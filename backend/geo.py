"""Geocoding (OSM Nominatim) + haversine distance for geofenced clock-ins."""
import math
from typing import Optional

import httpx

from config import logger

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_HEADERS = {"User-Agent": "HCOBNetwork/1.0 (ops@hcobcleaners.com)"}

CLOCKIN_RADIUS_M = 250.0


async def geocode_address(address: Optional[str]) -> Optional[dict]:
    """Address → {lat, lng} via Nominatim. Returns None if not resolvable."""
    if not address or not address.strip():
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                NOMINATIM_URL,
                params={"q": address.strip(), "format": "json", "limit": 1},
                headers=NOMINATIM_HEADERS,
            )
            resp.raise_for_status()
            data = resp.json()
        if not data:
            return None
        return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
    except Exception as e:
        logger.warning(f"Geocode failed for '{address[:60]}': {e}")
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two coordinates in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def resolve_gig_coords(db, gig: dict) -> Optional[dict]:
    """Gig site {lat,lng} — uses stored coords, else lazily geocodes once and caches."""
    if gig.get("site_lat") is not None and gig.get("site_lng") is not None:
        return {"lat": gig["site_lat"], "lng": gig["site_lng"]}
    if gig.get("geocode_attempted"):
        return None
    coords = await geocode_address(gig.get("address_line") or gig.get("location"))
    updates: dict = {"geocode_attempted": True}
    if coords:
        updates.update({"site_lat": coords["lat"], "site_lng": coords["lng"]})
    await db.gigs.update_one({"gig_id": gig["gig_id"]}, {"$set": updates})
    return coords
