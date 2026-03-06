"""
Drone Fleet Management & Dispatch Algorithm
============================================
Manages a fleet of drones and dispatches the nearest available one
to an incident using the Haversine formula.
"""

import math
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Drone Fleet — pre-configured with 5 drones at various locations
# Locations within 1-2 km of user at (13.114751, 77.634742) — North Bangalore, India
# ---------------------------------------------------------------------------

DRONE_FLEET = [
    {
        "id": "DRONE-01",
        "name": "Alpha Falcon",
        "latitude": 13.1195,
        "longitude": 77.6310,
        "battery": 95,
        "status": "idle",          # idle / responding / returning
        "speed_kmh": 80,
        "payload": "Medical Kit",
        "home_lat": 13.1195,
        "home_lon": 77.6310,
    },
    {
        "id": "DRONE-02",
        "name": "Beta Hawk",
        "latitude": 13.1100,
        "longitude": 77.6420,
        "battery": 88,
        "status": "idle",
        "speed_kmh": 75,
        "payload": "Fire Suppressant",
        "home_lat": 13.1100,
        "home_lon": 77.6420,
    },
    {
        "id": "DRONE-03",
        "name": "Gamma Eagle",
        "latitude": 13.1210,
        "longitude": 77.6390,
        "battery": 92,
        "status": "idle",
        "speed_kmh": 85,
        "payload": "Rescue Float",
        "home_lat": 13.1210,
        "home_lon": 77.6390,
    },
    {
        "id": "DRONE-04",
        "name": "Delta Osprey",
        "latitude": 13.1080,
        "longitude": 77.6280,
        "battery": 78,
        "status": "idle",
        "speed_kmh": 70,
        "payload": "AED + First Aid",
        "home_lat": 13.1080,
        "home_lon": 77.6280,
    },
    {
        "id": "DRONE-05",
        "name": "Echo Raptor",
        "latitude": 13.1170,
        "longitude": 77.6260,
        "battery": 100,
        "status": "idle",
        "speed_kmh": 90,
        "payload": "Search Light + Camera",
        "home_lat": 13.1170,
        "home_lon": 77.6260,
    },
]


import random

def haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth
    using the Haversine formula.

    Args:
        lat1, lon1: Coordinates of point 1 (degrees)
        lat2, lon2: Coordinates of point 2 (degrees)

    Returns:
        Distance in kilometers.
    """
    R = 6371.0  # Earth's radius in km

    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(d_lon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def reposition_fleet_near(lat: float, lon: float):
    """
    Reposition all idle drones to random offsets near the given coordinates.
    Offsets are between 0.005 and 0.025 degrees (approx 0.5-3 km).
    """
    logger.info(f"Repositioning fleet near ({lat}, {lon})")
    for drone in DRONE_FLEET:
        if drone["status"] == "idle":
            # Generate random offset (keeping it somewhat realistic)
            off_lat = random.uniform(0.008, 0.018) * random.choice([-1, 1])
            off_lon = random.uniform(0.008, 0.018) * random.choice([-1, 1])
            
            drone["latitude"] = lat + off_lat
            drone["longitude"] = lon + off_lon
            # Also update home position so "reset" doesn't jump them across the world
            drone["home_lat"] = drone["latitude"]
            drone["home_lon"] = drone["longitude"]
            
            logger.debug(f"   {drone['id']} moved to ({drone['latitude']:.4f}, {drone['longitude']:.4f})")


def get_fleet() -> list[dict]:
    """Return the current state of the drone fleet."""
    return DRONE_FLEET


def get_drone(drone_id: str) -> Optional[dict]:
    """Get a specific drone by ID."""
    for drone in DRONE_FLEET:
        if drone["id"] == drone_id:
            return drone
    return None


def dispatch_nearest(
    incident_lat: float, incident_lon: float
) -> Optional[dict]:
    """
    Find and dispatch the nearest available (idle) drone to an incident.

    Args:
        incident_lat: Latitude of the incident.
        incident_lon: Longitude of the incident.

    Returns:
        The dispatched drone dict, or None if no drones available.
    """
    available = [d for d in DRONE_FLEET if d["status"] == "idle"]

    if not available:
        logger.warning("No drones available for dispatch")
        return None

    # Calculate distances and sort
    distances = []
    for drone in available:
        dist = haversine(
            drone["latitude"], drone["longitude"],
            incident_lat, incident_lon,
        )
        distances.append((drone, dist))
        logger.debug(
            f"   {drone['id']} ({drone['name']}): {dist:.2f} km away"
        )

    distances.sort(key=lambda x: x[1])
    nearest_drone, distance = distances[0]

    # Dispatch the drone
    nearest_drone["status"] = "responding"
    eta_minutes = (distance / nearest_drone["speed_kmh"]) * 60

    logger.info(
        f"Dispatching {nearest_drone['id']} ({nearest_drone['name']}) - "
        f"{distance:.2f} km away, ETA: {eta_minutes:.1f} min"
    )

    return {
        "drone": nearest_drone,
        "distance_km": round(distance, 2),
        "eta_minutes": round(eta_minutes, 1),
    }


def reset_drone(drone_id: str):
    """Reset a drone back to idle status at its home position."""
    drone = get_drone(drone_id)
    if drone:
        drone["status"] = "idle"
        drone["latitude"] = drone["home_lat"]
        drone["longitude"] = drone["home_lon"]
        logger.info(f" {drone_id} reset to idle at home base")
