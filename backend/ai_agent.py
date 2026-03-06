"""
AI Agent Module — Multi-Provider Vision-based Incident Analysis
================================================================
Analyzes incident images using Google Gemini and Groq Vision APIs
to determine if they represent real emergencies. Falls back to local
Pillow-based color/histogram analysis when all API providers fail.

Chain: Gemini -> Groq -> Local Pillow Analysis -> Safety Fallback
"""

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

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Provider Configuration
# ---------------------------------------------------------------------------

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Gemini client
gemini_client = None
if GEMINI_API_KEY:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    logger.info("Gemini API configured")
else:
    logger.warning("GEMINI_API_KEY not set")

# Groq client
groq_client = None
if GROQ_API_KEY:
    groq_client = Groq(api_key=GROQ_API_KEY)
    logger.info("Groq API configured")
else:
    logger.warning("GROQ_API_KEY not set")

# Model names
GEMINI_MODEL = "gemini-2.0-flash"
GROQ_MODEL = "llama-3.2-11b-vision-preview"

# ---------------------------------------------------------------------------
# Analysis Prompt
# ---------------------------------------------------------------------------

ANALYSIS_PROMPT = """You are an AI emergency response analyst for a drone rescue system.
Analyze this image carefully and provide a structured emergency assessment.

Your task:
1. Determine if this image shows a REAL EMERGENCY or a NORMAL/SAFE scene.
2. If it's an emergency, classify the type and severity.
3. Identify all objects and hazards visible in the image.

Respond ONLY with valid JSON in this exact format (no markdown, no code fences):
{
    "is_emergency": true or false,
    "incident_type": "one of: Road Accident, Fire Emergency, Flood / Water Rescue, Medical Emergency, Natural Disaster, Structural Collapse, Unknown Emergency, Normal Scene",
    "priority": "one of: CRITICAL, HIGH, MEDIUM, LOW, NONE",
    "confidence": 0.0 to 1.0,
    "detected_objects": [
        {"label": "object name", "confidence": 0.0 to 1.0}
    ],
    "description": "Brief description of what you see in the image",
    "recommendation": "Recommended emergency response action",
    "risk_factors": ["list of identified risks or hazards"]
}

Rules:
- If the image shows a normal scene (e.g., regular street, park, selfie, food, etc.), set is_emergency to false, priority to NONE, and incident_type to "Normal Scene".
- Only set is_emergency to true if there are clear signs of danger, distress, or emergency.
- Be accurate with confidence scores — use lower values when uncertain.
- For CRITICAL priority: active fires, floods with people trapped, severe accidents with casualties.
- For HIGH priority: accidents, structural damage, medical emergencies.
- For MEDIUM priority: potential hazards, minor incidents.
- For LOW priority: suspicious but unclear situations.
"""


def analyze_image(image_path: str) -> dict:
    """
    Analyze an incident image using available AI vision providers.
    Tries Gemini first, then Groq as fallback.

    Args:
        image_path: Path to the incident image file.

    Returns:
        Structured report with emergency classification, detected objects,
        priority, and recommendations.
    """
    logger.info(f"Analyzing image: {image_path}")

    path = Path(image_path)
    if not path.exists():
        logger.warning(f"Image not found: {image_path}")
        return _fallback_report("Image file not found")

    # Try Gemini first
    if gemini_client:
        logger.info("Trying Gemini Vision API...")
        result = _analyze_with_gemini(path)
        if result:
            return result
        logger.warning("Gemini failed, trying Groq fallback...")

    # Fall back to Groq
    if groq_client:
        logger.info("Trying Groq Vision API...")
        result = _analyze_with_groq(path)
        if result:
            return result
        logger.warning("Groq also failed")

    # No providers available or all failed
    logger.error("All AI providers failed, trying local image analysis...")

    # Try local Pillow-based analysis
    result = _analyze_with_pillow(path)
    if result:
        return result

    logger.error("All analysis methods exhausted")
    return _fallback_report("All AI providers unavailable or failed")


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------

def _analyze_with_gemini(path: Path) -> dict | None:
    """Analyze image using Google Gemini Vision API."""
    try:
        uploaded_file = gemini_client.files.upload(
            file=path,
            config=types.UploadFileConfig(mime_type=_get_mime_type(path)),
        )
        logger.info(f"Image uploaded to Gemini: {uploaded_file.name}")

        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[ANALYSIS_PROMPT, uploaded_file],
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=1024,
            ),
        )

        report = _parse_ai_response(response.text, f"Google Gemini ({GEMINI_MODEL})")

        # Clean up uploaded file
        try:
            gemini_client.files.delete(name=uploaded_file.name)
        except Exception:
            pass

        return report

    except Exception as e:
        logger.error(f"   Gemini analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Groq Provider
# ---------------------------------------------------------------------------

def _analyze_with_groq(path: Path) -> dict | None:
    """Analyze image using Groq Vision API (Llama 3.2 Vision)."""
    try:
        # Encode image to base64 for Groq API
        image_data = path.read_bytes()
        b64_image = base64.b64encode(image_data).decode("utf-8")
        mime_type = _get_mime_type(path)

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
                                "url": f"data:{mime_type};base64,{b64_image}",
                            },
                        },
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=1024,
        )

        response_text = response.choices[0].message.content
        report = _parse_ai_response(response_text, f"Groq Llama Vision ({GROQ_MODEL})")
        return report

    except Exception as e:
        logger.error(f"   Groq analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Local Pillow-based Analysis (Offline Fallback)
# ---------------------------------------------------------------------------

# Color ranges (HSV-like heuristics applied to RGB)
_FIRE_COLORS = {"red", "orange", "dark_red", "yellow"}
_WATER_COLORS = {"blue", "dark_blue", "cyan"}
_SMOKE_COLORS = {"grey", "dark_grey", "light_grey"}
_VEGETATION_COLORS = {"green", "dark_green"}


def _classify_pixel(r: int, g: int, b: int) -> str:
    """Classify a single RGB pixel into a named color category."""
    brightness = (r + g + b) / 3

    if brightness < 30:
        return "black"
    if brightness > 230 and max(r, g, b) - min(r, g, b) < 30:
        return "white"

    # Grey detection
    if max(r, g, b) - min(r, g, b) < 40:
        if brightness < 80:
            return "dark_grey"
        if brightness < 170:
            return "grey"
        return "light_grey"

    # Red / fire tones
    if r > 150 and r > g * 1.4 and r > b * 1.4:
        if r > 200 and g > 100:
            return "orange"
        if brightness < 100:
            return "dark_red"
        return "red"

    # Yellow
    if r > 180 and g > 160 and b < 100:
        return "yellow"

    # Green
    if g > r * 1.2 and g > b * 1.2:
        if brightness < 100:
            return "dark_green"
        return "green"

    # Blue / water
    if b > r * 1.3 and b > g * 1.1:
        if brightness < 100:
            return "dark_blue"
        return "blue"

    # Cyan
    if g > 120 and b > 120 and r < 100:
        return "cyan"

    return "other"


def _analyze_with_pillow(path: Path) -> dict | None:
    """
    Analyze an image locally using Pillow color histogram heuristics.
    Detects potential fire, flood, smoke, and darkness patterns based on
    dominant color distribution. This is a best-effort offline fallback
    when cloud AI providers are unavailable.
    """
    try:
        img = Image.open(path).convert("RGB")

        # Resize for faster analysis (keep aspect ratio)
        img.thumbnail((200, 200))
        pixels = list(img.getdata())
        total = len(pixels)

        if total == 0:
            return None

        # Classify every pixel
        color_counts = Counter(_classify_pixel(r, g, b) for r, g, b in pixels)

        # Calculate percentages
        pct = {color: count / total for color, count in color_counts.items()}

        # Aggregate category percentages
        fire_pct = sum(pct.get(c, 0) for c in _FIRE_COLORS)
        water_pct = sum(pct.get(c, 0) for c in _WATER_COLORS)
        smoke_pct = sum(pct.get(c, 0) for c in _SMOKE_COLORS)
        dark_pct = pct.get("black", 0) + pct.get("dark_grey", 0)
        vegetation_pct = sum(pct.get(c, 0) for c in _VEGETATION_COLORS)

        # Overall image brightness
        avg_brightness = sum((r + g + b) / 3 for r, g, b in pixels) / total

        # Edge detection (basic variance = potential chaos/debris)
        widths = img.size[0]
        grey_img = img.convert("L")
        grey_pixels = list(grey_img.getdata())
        mean_grey = sum(grey_pixels) / len(grey_pixels)
        variance = sum((p - mean_grey) ** 2 for p in grey_pixels) / len(grey_pixels)

        # Build detected objects list
        detected_objects = []
        risk_factors = []
        incident_type = "Normal Scene"
        is_emergency = False
        priority = "NONE"
        confidence = 0.3  # Low baseline for heuristic analysis
        description_parts = []

        # --- Fire Detection ---
        if fire_pct > 0.25:
            is_emergency = True
            incident_type = "Fire Emergency"
            priority = "CRITICAL" if fire_pct > 0.40 else "HIGH"
            confidence = min(0.7, 0.3 + fire_pct)
            detected_objects.append({"label": "fire/flames", "confidence": round(fire_pct, 2)})
            risk_factors.append("High concentration of fire-colored pixels detected")
            description_parts.append(f"Fire-like colors detected ({fire_pct:.0%} of image)")

        elif fire_pct > 0.12:
            detected_objects.append({"label": "warm tones (possible fire)", "confidence": round(fire_pct, 2)})
            risk_factors.append("Elevated warm color tones")
            description_parts.append(f"Warm/fire-like tones present ({fire_pct:.0%})")

        # --- Smoke Detection ---
        if smoke_pct > 0.35:
            detected_objects.append({"label": "smoke/haze", "confidence": round(smoke_pct, 2)})
            risk_factors.append("Heavy smoke or haze detected")
            description_parts.append(f"Smoke/haze patterns detected ({smoke_pct:.0%})")
            if not is_emergency:
                is_emergency = True
                incident_type = "Fire Emergency"
                priority = "HIGH"
                confidence = min(0.6, 0.3 + smoke_pct * 0.5)

        # --- Water/Flood Detection ---
        if water_pct > 0.30:
            detected_objects.append({"label": "water/flooding", "confidence": round(water_pct, 2)})
            risk_factors.append("Large water body or potential flooding detected")
            description_parts.append(f"Water/flood patterns detected ({water_pct:.0%})")
            if not is_emergency or priority in ("NONE", "LOW"):
                is_emergency = True
                incident_type = "Flood / Water Rescue"
                priority = "HIGH" if water_pct > 0.50 else "MEDIUM"
                confidence = min(0.6, 0.3 + water_pct * 0.5)

        # --- Darkness (night/power outage) ---
        if dark_pct > 0.50:
            detected_objects.append({"label": "darkness/low visibility", "confidence": round(dark_pct, 2)})
            risk_factors.append("Very low visibility conditions")
            description_parts.append(f"Low light / darkness ({dark_pct:.0%})")

        # --- High visual chaos (structural damage, debris) ---
        if variance > 3500:
            detected_objects.append({"label": "high visual complexity", "confidence": round(min(variance / 6000, 1.0), 2)})
            risk_factors.append("High visual variance may indicate debris or structural damage")
            description_parts.append("Complex/chaotic visual patterns detected")
            if not is_emergency and variance > 5000:
                is_emergency = True
                incident_type = "Structural Collapse"
                priority = "MEDIUM"
                confidence = 0.35

        # --- Vegetation (generally safe indicator) ---
        if vegetation_pct > 0.40 and not is_emergency:
            detected_objects.append({"label": "vegetation/greenery", "confidence": round(vegetation_pct, 2)})
            description_parts.append(f"Vegetation/natural scene ({vegetation_pct:.0%})")

        # If nothing was detected, provide generic description
        if not description_parts:
            top_colors = color_counts.most_common(3)
            color_desc = ", ".join(f"{c} ({n/total:.0%})" for c, n in top_colors)
            description_parts.append(f"Standard scene. Dominant colors: {color_desc}")

        description = ". ".join(description_parts)
        recommendation = (
            "Deploy drone for immediate assessment and response."
            if is_emergency
            else "Deploy reconnaissance drone to verify scene safety."
        )

        report = {
            "is_emergency": is_emergency,
            "incident_type": incident_type,
            "priority": priority,
            "confidence": round(confidence, 2),
            "detected_objects": detected_objects,
            "object_count": len(detected_objects),
            "description": description,
            "recommendation": recommendation,
            "risk_factors": risk_factors,
            "matched_objects": [obj["label"] for obj in detected_objects],
            "analysis_model": "Local Pillow Heuristic Analysis (offline)",
        }

        logger.info(
            f"Local analysis complete: {report['incident_type']} "
            f"(priority={report['priority']}, emergency={report['is_emergency']}, "
            f"fire={fire_pct:.0%}, water={water_pct:.0%}, smoke={smoke_pct:.0%})"
        )
        return report

    except Exception as e:
        logger.error(f"   Local Pillow analysis failed: {e}")
        return None


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------

def _parse_ai_response(response_text: str, model_label: str) -> dict | None:
    """Parse the JSON response from any AI provider into a structured report."""
    try:
        text = response_text.strip()
        logger.info(f"AI raw response: {text[:200]}...")

        # Clean up response — remove markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1]  # Remove first line
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        ai_result = json.loads(text)

        report = {
            "is_emergency": ai_result.get("is_emergency", False),
            "incident_type": ai_result.get("incident_type", "Unknown Emergency"),
            "priority": ai_result.get("priority", "MEDIUM"),
            "confidence": ai_result.get("confidence", 0.5),
            "detected_objects": ai_result.get("detected_objects", []),
            "object_count": len(ai_result.get("detected_objects", [])),
            "description": ai_result.get("description", ""),
            "recommendation": ai_result.get("recommendation", "Deploy reconnaissance drone."),
            "risk_factors": ai_result.get("risk_factors", []),
            "matched_objects": [obj["label"] for obj in ai_result.get("detected_objects", [])],
            "analysis_model": model_label,
        }

        logger.info(
            f"Analysis complete [{model_label}]: {report['incident_type']} "
            f"(priority={report['priority']}, emergency={report['is_emergency']})"
        )
        return report

    except json.JSONDecodeError as e:
        logger.error(f"   Failed to parse AI response as JSON: {e}")
        return None


def _get_mime_type(path: Path) -> str:
    """Determine MIME type from file extension."""
    suffix = path.suffix.lower()
    mime_types = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
    }
    return mime_types.get(suffix, "image/jpeg")


def _fallback_report(reason: str) -> dict:
    """Return a fallback report when all AI providers fail."""
    return {
        "is_emergency": True,  # Err on side of caution
        "incident_type": "Unknown Emergency",
        "priority": "MEDIUM",
        "confidence": 0.0,
        "detected_objects": [],
        "object_count": 0,
        "description": f"AI analysis unavailable: {reason}",
        "recommendation": "Deploy reconnaissance drone for manual assessment.",
        "risk_factors": [],
        "matched_objects": [],
        "analysis_model": "Fallback (all providers unavailable)",
    }
