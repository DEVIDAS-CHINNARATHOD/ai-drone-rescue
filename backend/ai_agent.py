"""
AI Agent Module — Multi-Provider Vision-based Incident Analysis
================================================================
Analyzes incident images using Google Gemini and Groq Vision APIs
to determine if they represent real emergencies. Tries Gemini first,
falls back to Groq if Gemini fails.
"""

import os
import json
import base64
import logging
from pathlib import Path

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
GEMINI_MODEL = "gemini-1.5-flash"
GROQ_MODEL = "llama-3.2-90b-vision-preview"

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
    logger.error("All AI providers failed")
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
