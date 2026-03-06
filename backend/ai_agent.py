"""
AI Agent Module — Image Analysis & Incident Classification
==========================================================
Analyzes incident images to detect objects and classify emergency types.
Uses a rule-based approach optimized for hackathon speed (no heavy model downloads).
"""

import random
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Simulated object detection (replaces YOLO for hackathon portability)
# In production, swap this with ultralytics YOLOv8:
#   from ultralytics import YOLO
#   model = YOLO("yolov8n.pt")
#   results = model(image_path)
# ---------------------------------------------------------------------------

# Objects the system can "detect"
DETECTABLE_OBJECTS = [
    "person", "car", "fire", "smoke", "water", "truck",
    "bicycle", "motorcycle", "debris", "building",
]

# Incident classification rules
CLASSIFICATION_RULES = [
    {
        "required": {"car"},
        "optional": {"person", "debris", "truck", "motorcycle"},
        "type": "Road Accident",
        "priority": "HIGH",
    },
    {
        "required": {"fire"},
        "optional": {"smoke", "building", "debris"},
        "type": "Fire Emergency",
        "priority": "CRITICAL",
    },
    {
        "required": {"water", "person"},
        "optional": {"debris", "building"},
        "type": "Flood / Water Rescue",
        "priority": "CRITICAL",
    },
    {
        "required": {"person"},
        "optional": {"debris", "building"},
        "type": "Medical Emergency",
        "priority": "HIGH",
    },
]


def _simulate_object_detection(image_path: str) -> list[dict]:
    """
    Simulate object detection on an image.
    In a real system, this would use YOLOv8 / Vision AI.
    Returns a list of detected objects with confidence scores.
    """
    # Check if image exists
    path = Path(image_path)
    if not path.exists():
        logger.warning(f"Image not found: {image_path}")
        return []

    # Get file size to seed randomness (makes results deterministic per image)
    file_size = path.stat().st_size
    rng = random.Random(file_size)

    # "Detect" 2-5 objects based on image characteristics
    num_objects = rng.randint(2, 5)
    detected = []

    # Always include at least one meaningful object for demo purposes
    primary_objects = ["person", "car", "fire", "smoke", "water"]
    primary = rng.choice(primary_objects)
    detected.append({
        "label": primary,
        "confidence": round(rng.uniform(0.75, 0.98), 2),
        "bbox": [
            rng.randint(10, 200),
            rng.randint(10, 200),
            rng.randint(201, 500),
            rng.randint(201, 500),
        ],
    })

    # Add more objects
    remaining = [obj for obj in DETECTABLE_OBJECTS if obj != primary]
    for obj in rng.sample(remaining, min(num_objects - 1, len(remaining))):
        detected.append({
            "label": obj,
            "confidence": round(rng.uniform(0.50, 0.95), 2),
            "bbox": [
                rng.randint(10, 200),
                rng.randint(10, 200),
                rng.randint(201, 500),
                rng.randint(201, 500),
            ],
        })

    return detected


def _classify_incident(detected_objects: list[dict]) -> dict:
    """
    Classify the incident type based on detected objects.
    Uses rule-based matching against classification rules.
    """
    labels = {obj["label"] for obj in detected_objects}

    for rule in CLASSIFICATION_RULES:
        if rule["required"].issubset(labels):
            matching_optional = labels & rule["optional"]
            confidence = min(
                0.95,
                0.6 + 0.1 * len(matching_optional) + 0.1 * len(rule["required"]),
            )
            return {
                "incident_type": rule["type"],
                "priority": rule["priority"],
                "confidence": round(confidence, 2),
                "matched_objects": list(rule["required"] | matching_optional),
            }

    # Fallback — unknown incident
    return {
        "incident_type": "Unknown Emergency",
        "priority": "MEDIUM",
        "confidence": 0.40,
        "matched_objects": list(labels),
    }


def analyze_image(image_path: str) -> dict:
    """
    Main analysis function — detects objects and classifies the incident.

    Args:
        image_path: Path to the incident image file.

    Returns:
        Structured report with detected objects, incident type, priority, etc.
    """
    logger.info(f"🔍 Analyzing image: {image_path}")

    # Step 1: Detect objects
    detected_objects = _simulate_object_detection(image_path)
    logger.info(f"   Detected {len(detected_objects)} objects: "
                f"{[o['label'] for o in detected_objects]}")

    # Step 2: Classify incident
    classification = _classify_incident(detected_objects)
    logger.info(f"   Classification: {classification['incident_type']} "
                f"(priority={classification['priority']})")

    # Step 3: Build structured report
    report = {
        "detected_objects": detected_objects,
        "object_count": len(detected_objects),
        "incident_type": classification["incident_type"],
        "priority": classification["priority"],
        "confidence": classification["confidence"],
        "matched_objects": classification["matched_objects"],
        "analysis_model": "RuleBasedDetector-v1 (YOLOv8-compatible API)",
        "recommendation": _get_recommendation(classification["incident_type"]),
    }

    return report


def _get_recommendation(incident_type: str) -> str:
    """Generate response recommendation based on incident type."""
    recommendations = {
        "Road Accident": "Deploy medical drone with first-aid kit. Alert nearest hospital and traffic control.",
        "Fire Emergency": "Deploy fire-suppression drone. Alert fire department. Evacuate area.",
        "Flood / Water Rescue": "Deploy rescue drone with flotation device. Alert coast guard.",
        "Medical Emergency": "Deploy medical drone with AED and first-aid kit. Alert paramedics.",
        "Unknown Emergency": "Deploy reconnaissance drone for situation assessment. Standby rescue teams.",
    }
    return recommendations.get(incident_type, recommendations["Unknown Emergency"])
