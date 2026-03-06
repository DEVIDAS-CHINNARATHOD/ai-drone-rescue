"""
Drone Movement Simulation
=========================
Simulates a drone moving step-by-step toward an incident location.
Broadcasts position updates via WebSocket every second.
"""

import asyncio
import json
import math
import logging
from typing import Any
from drone_dispatch import DRONE_FLEET, haversine

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WebSocket Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages WebSocket connections for broadcasting drone position updates."""

    def __init__(self):
        self.active_connections: list[Any] = []

    async def connect(self, websocket):
        """Accept and store a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client connected ({len(self.active_connections)} total)")

    def disconnect(self, websocket):
        """Remove a disconnected WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client disconnected ({len(self.active_connections)} total)")

    async def broadcast(self, message: dict):
        """Send a JSON message to all connected clients."""
        dead = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)
        # Clean up dead connections
        for conn in dead:
            self.disconnect(conn)


# Global connection manager instance
ws_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Drone Movement Simulation
# ---------------------------------------------------------------------------

def _interpolate_position(
    current_lat: float, current_lon: float,
    target_lat: float, target_lon: float,
    step_fraction: float,
) -> tuple[float, float]:
    """
    Linearly interpolate between current position and target.
    step_fraction is how far to move (0.0 to 1.0).
    """
    new_lat = current_lat + (target_lat - current_lat) * step_fraction
    new_lon = current_lon + (target_lon - current_lon) * step_fraction
    return round(new_lat, 6), round(new_lon, 6)


def _calculate_bearing(lat1, lon1, lat2, lon2) -> float:
    """Calculate the bearing between two points."""
    d_lon = math.radians(lon2 - lon1)
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)

    x = math.sin(d_lon) * math.cos(lat2_r)
    y = (
        math.cos(lat1_r) * math.sin(lat2_r)
        - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(d_lon)
    )
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


async def simulate_drone_movement(
    drone: dict,
    target_lat: float,
    target_lon: float,
    incident_id: str,
    total_steps: int = 20,
    interval_seconds: float = 1.0,
):
    """
    Simulate a drone moving step-by-step toward the incident location.
    Broadcasts position updates via WebSocket at each step.

    Args:
        drone:             Drone dict (will be mutated with new position).
        target_lat:        Incident latitude.
        target_lon:        Incident longitude.
        incident_id:       ID of the incident being responded to.
        total_steps:       Number of movement steps (default 20).
        interval_seconds:  Seconds between each step (default 1.0).
    """
    start_lat = drone["latitude"]
    start_lon = drone["longitude"]
    drone_id = drone["id"]

    logger.info(
        f"Starting simulation: {drone_id} -> "
        f"({target_lat}, {target_lon}) in {total_steps} steps"
    )

    # Broadcast initial departure
    await ws_manager.broadcast({
        "type": "drone_departed",
        "drone_id": drone_id,
        "drone_name": drone.get("name", drone_id),
        "incident_id": incident_id,
        "start": {"lat": start_lat, "lon": start_lon},
        "target": {"lat": target_lat, "lon": target_lon},
        "total_steps": total_steps,
    })

    for step in range(1, total_steps + 1):
        fraction = step / total_steps
        new_lat, new_lon = _interpolate_position(
            start_lat, start_lon, target_lat, target_lon, fraction
        )

        # Update drone position
        drone["latitude"] = new_lat
        drone["longitude"] = new_lon

        # Simulate battery drain
        drone["battery"] = max(0, drone["battery"] - 0.3)

        # Calculate bearing for realistic heading
        bearing = _calculate_bearing(
            drone["latitude"], drone["longitude"], target_lat, target_lon
        )

        # Calculate current distance to target
        current_dist = haversine(
            drone["latitude"], drone["longitude"],
            target_lat, target_lon
        )

        # Broadcast position update
        update = {
            "type": "drone_position",
            "drone_id": drone_id,
            "drone_name": drone.get("name", drone_id),
            "incident_id": incident_id,
            "step": step,
            "total_steps": total_steps,
            "latitude": drone["latitude"],
            "longitude": drone["longitude"],
            "bearing": round(bearing, 1),
            "battery": round(drone["battery"], 1),
            "progress_pct": round(fraction * 100, 1),
            "status": "en_route",
            "distance_km": round(current_dist, 2),
        }

        await ws_manager.broadcast(update)
        logger.debug(f"   Step {step}/{total_steps}: ({new_lat}, {new_lon})")

        await asyncio.sleep(interval_seconds)

    # Drone has arrived
    drone["status"] = "responding"
    drone["latitude"] = target_lat
    drone["longitude"] = target_lon

    arrival_msg = {
        "type": "drone_arrived",
        "drone_id": drone_id,
        "drone_name": drone.get("name", drone_id),
        "incident_id": incident_id,
        "latitude": target_lat,
        "longitude": target_lon,
        "battery": round(drone["battery"], 1),
    }
    await ws_manager.broadcast(arrival_msg)

    # Trigger auto-capture on the drone camera frontend
    await ws_manager.broadcast({
        "type": "capture_camera",
        "incident_id": incident_id,
        "drone_id": drone_id
    })

    logger.info(f"{drone_id} arrived at incident {incident_id}")

    return arrival_msg
