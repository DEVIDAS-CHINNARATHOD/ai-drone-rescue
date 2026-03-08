import os
import json
import base64
import logging
from pathlib import Path
from collections import Counter

from PIL import Image
from google import genai
from google.genai import types
from groq import Groq
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

gemini_client = None
groq_client = None

if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)

GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.2-11b-vision-preview"

ANALYSIS_PROMPT = """You are an AI emergency response analyst for a drone rescue system.

Analyze the provided image and determine if it represents a real emergency.

Respond ONLY with valid JSON in this format:

{
"is_emergency": true or false,
"incident_type": "...",
"priority": "CRITICAL | HIGH | MEDIUM | LOW | NONE",
"confidence": 0.0 to 1.0,
"detected_objects": [{"label":"...", "confidence":0.0}],
"description": "...",
"recommendation": "...",
"risk_factors": ["..."]
}
"""

def analyze_image(image_path: str) -> dict:

    path = Path(image_path)

    if not path.exists():
        return _fallback_report("Image file not found")

    if path.suffix.lower() not in [".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"]:
        return _fallback_report("Unsupported image format")

    if gemini_client:
        result = _analyze_with_gemini(path)
        if result:
            return result

    if groq_client:
        result = _analyze_with_groq(path)
        if result:
            return result

    result = _analyze_with_pillow(path)

    if result:
        return result

    return _fallback_report("All AI providers failed")


def _analyze_with_gemini(path: Path):

    try:

        uploaded_file = gemini_client.files.upload(
            file=path,
            config=types.UploadFileConfig(
                mime_type=_get_mime_type(path)
            )
        )

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[ANALYSIS_PROMPT, uploaded_file],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1024
            )
        )

        report = _parse_ai_response(response.text, "Google Gemini")

        try:
            gemini_client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

        return report

    except Exception:
        return None


def _analyze_with_groq(path: Path):

    try:

        image_bytes = path.read_bytes()
        b64 = base64.b64encode(image_bytes).decode()

        mime = _get_mime_type(path)

        response = groq_client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": ANALYSIS_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime};base64,{b64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1,
            max_tokens=1024
        )

        text = response.choices[0].message.content
        return _parse_ai_response(text, "Groq Llama Vision")

    except Exception:
        return None


_FIRE = {"red", "orange", "yellow"}
_WATER = {"blue", "cyan"}
_SMOKE = {"grey", "dark_grey"}


def _classify_pixel(r, g, b):

    brightness = (r + g + b) / 3

    if brightness < 40:
        return "black"

    if r > g * 1.3 and r > b * 1.3:
        return "red"

    if b > r * 1.2 and b > g * 1.2:
        return "blue"

    if abs(r - g) < 20 and abs(g - b) < 20:
        return "grey"

    return "other"


def _analyze_with_pillow(path: Path):

    try:

        img = Image.open(path).convert("RGB")
        img.thumbnail((160, 160))

        pixels = list(img.getdata())
        total = len(pixels)

        colors = Counter(_classify_pixel(r, g, b) for r, g, b in pixels)

        fire_pct = colors["red"] / total
        water_pct = colors["blue"] / total
        smoke_pct = colors["grey"] / total

        is_emergency = False
        incident_type = "Normal Scene"
        priority = "NONE"
        confidence = 0.3

        detected = []
        risks = []

        if fire_pct > 0.25:
            is_emergency = True
            incident_type = "Fire Emergency"
            priority = "CRITICAL"
            confidence = 0.6
            detected.append({"label": "fire", "confidence": fire_pct})
            risks.append("Large fire-like color region")

        elif water_pct > 0.35:
            is_emergency = True
            incident_type = "Flood / Water Rescue"
            priority = "HIGH"
            confidence = 0.5
            detected.append({"label": "water", "confidence": water_pct})
            risks.append("Large water body detected")

        elif smoke_pct > 0.40:
            is_emergency = True
            incident_type = "Smoke / Fire Risk"
            priority = "MEDIUM"
            confidence = 0.45
            detected.append({"label": "smoke", "confidence": smoke_pct})

        return {
            "is_emergency": is_emergency,
            "incident_type": incident_type,
            "priority": priority,
            "confidence": round(confidence, 2),
            "detected_objects": detected,
            "object_count": len(detected),
            "description": "Local heuristic image analysis",
            "recommendation": "Deploy drone for verification",
            "risk_factors": risks,
            "matched_objects": [x["label"] for x in detected],
            "analysis_model": "Local Pillow Analysis"
        }

    except Exception:
        return None


def _parse_ai_response(text, model):

    try:

        text = text.strip()

        if text.startswith("```"):
            text = text.split("\n", 1)[1].rstrip("```")

        data = json.loads(text)

        objects = data.get("detected_objects", [])

        return {
            "is_emergency": data.get("is_emergency", False),
            "incident_type": data.get("incident_type", "Unknown"),
            "priority": data.get("priority", "MEDIUM"),
            "confidence": data.get("confidence", 0.5),
            "detected_objects": objects,
            "object_count": len(objects),
            "description": data.get("description", ""),
            "recommendation": data.get("recommendation", ""),
            "risk_factors": data.get("risk_factors", []),
            "matched_objects": [o["label"] for o in objects],
            "analysis_model": model
        }

    except Exception:
        return None


def _get_mime_type(path: Path):

    ext = path.suffix.lower()

    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif"
    }.get(ext, "image/jpeg")


def _fallback_report(reason):

    return {
        "is_emergency": False,
        "incident_type": "Unverified Scene",
        "priority": "LOW",
        "confidence": 0.0,
        "detected_objects": [],
        "object_count": 0,
        "description": f"AI unavailable: {reason}",
        "recommendation": "Send reconnaissance drone",
        "risk_factors": [],
        "matched_objects": [],
        "analysis_model": "Fallback"
    }
