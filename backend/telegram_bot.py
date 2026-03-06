"""
Telegram Bot Integration
========================
Handles photo + location messages from Telegram users
and forwards them as incidents to the FastAPI backend.
"""

import os
import logging
import asyncio
import httpx
from pathlib import Path
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:10000")

# Temporary storage for user sessions (photo → location flow)
user_sessions: dict[int, dict] = {}


# ---------------------------------------------------------------------------
# Bot Handlers
# ---------------------------------------------------------------------------

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    welcome = (
        "🚁 *AI Drone Emergency Response System*\n\n"
        "Report an emergency in 2 steps:\n\n"
        "1️⃣ Send a *photo* of the incident\n"
        "2️⃣ Share your *location* 📍\n\n"
        "Our AI will analyze the image and dispatch the nearest drone!\n\n"
        "Type /help for more info."
    )
    await update.message.reply_text(welcome, parse_mode="Markdown")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    help_text = (
        "📖 *How to use:*\n\n"
        "• Send a photo of the emergency\n"
        "• Then share your GPS location\n"
        "• The system will:\n"
        "  🤖 Analyze the image with AI\n"
        "  🚁 Dispatch the nearest drone\n"
        "  🗺️ Show live tracking on the map\n\n"
        "Commands:\n"
        "/start — Welcome message\n"
        "/help — This help text\n"
        "/status — Check system status"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")


async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /status command — check backend health."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{SERVER_URL}/drones", timeout=5)
            drones = resp.json()
            idle = sum(1 for d in drones if d["status"] == "idle")
            text = (
                f"*System Online*\n\n"
                f" Total Drones: {len(drones)}\n"
                f" Available: {idle}\n"
                f" Busy: {len(drones) - idle}"
            )
    except Exception:
        text = " *System Offline* — Backend not reachable."

    await update.message.reply_text(text, parse_mode="Markdown")


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming photo — save it and wait for location."""
    user_id = update.message.from_user.id
    photo = update.message.photo[-1]  # Highest resolution

    # Download the photo
    file = await context.bot.get_file(photo.file_id)
    download_path = f"/tmp/telegram_{user_id}_{photo.file_id}.jpg"
    await file.download_to_drive(download_path)

    # Store in session
    user_sessions[user_id] = {
        "photo_path": download_path,
        "file_id": photo.file_id,
    }

    logger.info(f"📸 Photo received from user {user_id}")

    await update.message.reply_text(
        "📸 Photo received! Now please share your *location* 📍\n\n"
        "Tap the 📎 attachment icon → Location → Send your current location.",
        parse_mode="Markdown",
    )


async def handle_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming location — pair with photo and create incident."""
    user_id = update.message.from_user.id
    location = update.message.location

    if user_id not in user_sessions or "photo_path" not in user_sessions[user_id]:
        await update.message.reply_text(
            "⚠️ Please send a *photo* first, then share your location.",
            parse_mode="Markdown",
        )
        return

    session = user_sessions.pop(user_id)
    photo_path = session["photo_path"]

    await update.message.reply_text("🔄 Processing your report...")

    # Send incident to backend
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            with open(photo_path, "rb") as f:
                resp = await client.post(
                    f"{SERVER_URL}/incident",
                    data={
                        "latitude": str(location.latitude),
                        "longitude": str(location.longitude),
                    },
                    files={"image": ("incident.jpg", f, "image/jpeg")},
                )

            if resp.status_code == 200:
                result = resp.json()
                incident = result.get("incident", {})
                drone_info = result.get("dispatch", {})
                drone = drone_info.get("drone", {})

                report = (
                    f"🚨 *Incident Reported Successfully!*\n\n"
                    f"📋 *ID:* `{incident.get('incident_id', 'N/A')}`\n"
                    f"🔥 *Type:* {incident.get('incident_type', 'Analyzing...')}\n"
                    f"⚡ *Priority:* {incident.get('priority', 'N/A')}\n\n"
                    f"🚁 *Drone Dispatched:* {drone.get('name', 'N/A')}\n"
                    f"📏 *Distance:* {drone_info.get('distance_km', '?')} km\n"
                    f"⏱️ *ETA:* {drone_info.get('eta_minutes', '?')} min\n\n"
                    f"🗺️ Track live on the map dashboard!"
                )
                await update.message.reply_text(report, parse_mode="Markdown")
            else:
                await update.message.reply_text(
                    f"❌ Error creating incident (HTTP {resp.status_code})"
                )

    except Exception as e:
        logger.error(f"Error sending incident: {e}")
        await update.message.reply_text(
            "❌ Failed to connect to the server. Please try again later."
        )

    # Clean up temp file
    try:
        Path(photo_path).unlink(missing_ok=True)
    except Exception:
        pass


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any unrecognized message."""
    await update.message.reply_text(
        "🤖 I can help with emergency reporting!\n"
        "Send a *photo* of the incident, then share your *location*.\n"
        "Type /help for instructions.",
        parse_mode="Markdown",
    )


# ---------------------------------------------------------------------------
# Bot Runner
# ---------------------------------------------------------------------------

def create_bot_application() -> Application:
    """Create and configure the Telegram bot application."""
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN == "your_telegram_bot_token_here":
        logger.warning(
            "⚠️  TELEGRAM_BOT_TOKEN not set — Telegram bot will not start. "
            "Set it in backend/.env to enable Telegram integration."
        )
        return None

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Register handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_unknown
    ))

    logger.info("🤖 Telegram bot configured successfully")
    return app


async def run_bot():
    """Run the Telegram bot polling loop with retry logic."""
    max_retries = 5
    retry_delay = 5  # seconds

    for attempt in range(1, max_retries + 1):
        app = create_bot_application()
        if app is None:
            return

        try:
            logger.info(f"🤖 Starting Telegram bot polling (attempt {attempt}/{max_retries})...")

            # Delete any existing webhook to avoid conflicts
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                token = TELEGRAM_BOT_TOKEN
                await client.post(f"https://api.telegram.org/bot{token}/deleteWebhook",
                                  params={"drop_pending_updates": "true"})
                logger.info("   Cleared webhook and pending updates")

            await app.initialize()
            await app.start()
            await app.updater.start_polling(
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES,
            )

            logger.info("✅ Telegram bot is now polling successfully!")

            # Persistence loop to keep the coroutine alive
            while True:
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            logger.info("🛑 Telegram bot stopping...")
            break
        except Exception as e:
            logger.error(f"❌ Telegram bot error (attempt {attempt}): {e}")
            if attempt < max_retries:
                logger.info(f"   Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
            else:
                logger.error("❌ Telegram bot failed after all retries.")
        finally:
            try:
                if app.updater and app.updater.running:
                    await app.updater.stop()
                if app.running:
                    await app.stop()
                await app.shutdown()
            except Exception as e:
                logger.debug(f"Bot cleanup: {e}")
