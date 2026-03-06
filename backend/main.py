"""
AI Drone Emergency Response System — FastAPI Backend
=====================================================
Main server handling incidents, drone dispatch, WebSocket updates,
image uploads, and Telegram bot integration.
"""

import os
import uuid
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Local modules
from ai_agent import analyze_image
from drone_dispatch import dispatch_nearest, get_fleet, get_drone, reset_drone, reposition_fleet_near
from drone_simulation import ws_manager, simulate_drone_movement
from telegram_bot import run_bot

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("main")

# Paths
BASE_DIR = Path(__file__).parent.parent
IMAGES_DIR = BASE_DIR / "images"
IMAGES_DIR.mkdir(exist_ok=True)


# ---------------------------------------------------------------------------
# In-memory data stores
# ---------------------------------------------------------------------------

incidents: list[dict] = []
uploaded_images: dict[str, list[str]] = {}  # incident_id → [image_paths]


# ---------------------------------------------------------------------------
# App Lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info("=" * 60)
    logger.info("🚁 AI Drone Emergency Response System — Starting Up")
    logger.info("=" * 60)

    # Start Telegram bot in background
    bot_task = asyncio.create_task(run_bot())

    yield

    logger.info("🛑 Shutting down...")
    bot_task.cancel()


# ---------------------------------------------------------------------------
# FastAPI App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Drone Emergency Response System",
    description="Real-time drone dispatch for emergency incidents",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins for hackathon
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve uploaded images
app.mount("/images", StaticFiles(directory=str(IMAGES_DIR)), name="images")


# ---------------------------------------------------------------------------
# REST Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "AI Drone Emergency Response System",
        "status": "online",
        "version": "1.0.0",
        "endpoints": {
            "POST /incident": "Report a new incident",
            "GET /incidents": "List all incidents",
            "GET /drones": "Get drone fleet status",
            "POST /upload-image/{incident_id}": "Upload drone camera image",
            "WS /ws": "WebSocket for live drone updates",
        },
    }


@app.post("/incident")
async def create_incident(
    latitude: float = Form(...),
    longitude: float = Form(...),
    image: UploadFile = File(...),
):
    """
    Create a new incident from a photo and GPS coordinates.
    1. Save the image
    2. Run AI analysis
    3. Dispatch nearest drone
    4. Start drone simulation
    """
    incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
    timestamp = datetime.utcnow().isoformat()

    logger.info(f"🚨 New incident {incident_id} at ({latitude}, {longitude})")

    # Step 1: Save the uploaded image
    image_filename = f"{incident_id}_{image.filename}"
    image_path = IMAGES_DIR / image_filename
    content = await image.read()
    with open(image_path, "wb") as f:
        f.write(content)
    logger.info(f"   📸 Image saved: {image_filename}")

    # Step 2: AI analysis
    try:
        ai_report = analyze_image(str(image_path))
    except Exception as e:
        logger.error(f"   AI analysis failed: {e}")
        ai_report = {
            "incident_type": "Unknown Emergency",
            "priority": "MEDIUM",
            "confidence": 0.0,
            "detected_objects": [],
            "recommendation": "Deploy reconnaissance drone.",
        }

    # Step 3: Create incident record
    incident = {
        "incident_id": incident_id,
        "latitude": latitude,
        "longitude": longitude,
        "image": f"/images/{image_filename}",
        "incident_type": ai_report["incident_type"],
        "priority": ai_report["priority"],
        "timestamp": timestamp,
        "ai_report": ai_report,
        "status": "active",
        "drone_assigned": None,
        "uploaded_images": [],
    }

    # Step 4: Reposition fleet and dispatch nearest drone
    reposition_fleet_near(latitude, longitude)
    
    # Broadcast fleet repositioning to map
    await ws_manager.broadcast({
        "type": "fleet_repositioned",
        "drones": get_fleet(),
        "incident_lat": latitude,
        "incident_lon": longitude,
    })

    dispatch_result = dispatch_nearest(latitude, longitude)

    if dispatch_result:
        drone = dispatch_result["drone"]
        incident["drone_assigned"] = {
            "drone_id": drone["id"],
            "drone_name": drone["name"],
            "distance_km": dispatch_result["distance_km"],
            "eta_minutes": dispatch_result["eta_minutes"],
        }

        # Step 5: Start drone simulation in background
        asyncio.create_task(
            simulate_drone_movement(
                drone=drone,
                target_lat=latitude,
                target_lon=longitude,
                incident_id=incident_id,
                total_steps=25,
                interval_seconds=1.0,
            )
        )
        logger.info(f"   🚁 Drone {drone['id']} dispatched, simulation started")
    else:
        logger.warning(f"   ⚠️  No drones available for {incident_id}")

    incidents.append(incident)
    uploaded_images[incident_id] = []

    # Broadcast new incident to WebSocket clients
    await ws_manager.broadcast({
        "type": "new_incident",
        "incident": incident,
    })

    return {
        "status": "success",
        "incident": incident,
        "dispatch": dispatch_result,
    }


@app.delete("/incidents")
async def clear_all_incidents():
    """
    Clear all incidents and reset all drones.
    """
    global incidents, uploaded_images
    
    # 1. Clear backend data
    incidents = []
    uploaded_images = {}
    
    # 2. Reset all drones to home
    for drone in get_fleet():
        reset_drone(drone["id"])
    
    # 3. Broadcast reset to all clients
    await ws_manager.broadcast({
        "type": "system_reset",
        "message": "All incidents cleared and drones reset."
    })
    
    return {
        "status": "success",
        "message": "System reset successfully"
    }


@app.get("/incidents")
async def list_incidents():
    """Return all incidents."""
    return incidents


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """Return a specific incident by ID."""
    for inc in incidents:
        if inc["incident_id"] == incident_id:
            inc_copy = dict(inc)
            inc_copy["uploaded_images"] = uploaded_images.get(incident_id, [])
            return inc_copy
    raise HTTPException(status_code=404, detail="Incident not found")


@app.get("/drones")
async def list_drones():
    """Return the current state of all drones."""
    return get_fleet()


@app.get("/drones/{drone_id}")
async def get_drone_status(drone_id: str):
    """Return a specific drone's status."""
    drone = get_drone(drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")
    return drone


@app.post("/drones/{drone_id}/reset")
async def reset_drone_endpoint(drone_id: str):
    """Reset a drone to idle status at home base."""
    drone = get_drone(drone_id)
    if not drone:
        raise HTTPException(status_code=404, detail="Drone not found")
    reset_drone(drone_id)
    return {"status": "success", "message": f"{drone_id} reset to idle"}


@app.post("/upload-image/{incident_id}")
async def upload_drone_image(
    incident_id: str,
    image: UploadFile = File(...),
):
    """
    Upload an image captured by the drone camera.
    These are stored and shown on the rescue team dashboard.
    """
    # Verify incident exists
    incident = None
    for inc in incidents:
        if inc["incident_id"] == incident_id:
            incident = inc
            break

    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Save image
    image_filename = f"{incident_id}_drone_{uuid.uuid4().hex[:6]}.jpg"
    image_path = IMAGES_DIR / image_filename
    content = await image.read()
    with open(image_path, "wb") as f:
        f.write(content)

    image_url = f"/images/{image_filename}"

    # Track uploaded images
    if incident_id not in uploaded_images:
        uploaded_images[incident_id] = []
    uploaded_images[incident_id].append(image_url)

    logger.info(f"📷 Drone image uploaded for {incident_id}: {image_filename}")

    # Broadcast to dashboard clients
    await ws_manager.broadcast({
        "type": "drone_image_uploaded",
        "incident_id": incident_id,
        "image_url": image_url,
    })

    return {
        "status": "success",
        "incident_id": incident_id,
        "image_url": image_url,
        "total_images": len(uploaded_images[incident_id]),
    }




# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time drone position updates."""
    await ws_manager.connect(websocket)
    try:
        while True:
            # Keep connection alive; handle any client messages
            data = await websocket.receive_text()
            # Echo back or handle commands
            if data == "ping":
                await websocket.send_json({"type": "pong"})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# Error Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
