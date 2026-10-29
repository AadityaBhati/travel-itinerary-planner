import logging
from abc import ABC, abstractmethod

import httpx

from .schemas import Place, RouteLeg, TripRequest

logger = logging.getLogger(__name__)


class MapsProvider(ABC):
    @abstractmethod
    async def search(self, query: str, limit: int = 6) -> list[Place]: ...

    @abstractmethod
    async def route(self, places: list[Place]) -> list[RouteLeg]: ...

    async def close(self) -> None:
        return None


class OSMMapsProvider(MapsProvider):
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=10.0,
            headers={"User-Agent": "Wayfinder travel planner/1.0"},
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def search(self, query: str, limit: int = 6) -> list[Place]:
        if not query.strip():
            return []
        response = await self.client.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": query, "format": "jsonv2", "limit": min(limit, 10), "addressdetails": 1},
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            return []
        results: list[Place] = []
        for item in payload:
            if not isinstance(item, dict):
                continue
            try:
                osm_id = str(item["osm_id"])
                results.append(Place(
                    id=f"osm:{item.get('osm_type', 'place')}:{osm_id}",
                    name=str(item.get("display_name", query)).split(",")[0],
                    latitude=float(item["lat"]),
                    longitude=float(item["lon"]),
                    category=str(item.get("type") or item.get("class") or "place"),
                    provider="osm",
                    source_url=f"https://www.openstreetmap.org/{item.get('osm_type', 'node')}/{osm_id}",
                    address=item.get("display_name"),
                ))
            except (KeyError, TypeError, ValueError):
                continue
        return results

    async def route(self, places: list[Place]) -> list[RouteLeg]:
        legs: list[RouteLeg] = []
        for start, end in zip(places, places[1:]):
            response = await self.client.get(
                f"https://router.project-osrm.org/route/v1/driving/{start.longitude},{start.latitude};{end.longitude},{end.latitude}",
                params={"overview": "full", "geometries": "geojson"},
            )
            response.raise_for_status()
            payload = response.json()
            route = (payload.get("routes") or [{}])[0]
            geometry = route.get("geometry", {}).get("coordinates", [])
            legs.append(RouteLeg(
                from_place_id=start.id,
                to_place_id=end.id,
                distance_km=float(route.get("distance", 0)) / 1000,
                duration_minutes=float(route.get("duration", 0)) / 60,
                geometry=[[float(point[1]), float(point[0])] for point in geometry if len(point) >= 2],
            ))
        return legs


def build_maps_provider(settings) -> MapsProvider:
    if settings.maps_provider != "osm":
        logger.warning("unsupported maps provider=%s; using OSM fallback", settings.maps_provider)
    return OSMMapsProvider()


async def build_grounded_context(provider: MapsProvider, request: TripRequest) -> tuple[list[Place], list[RouteLeg]]:
    places = [place for place in ([request.origin] if request.origin else []) + request.destinations if place]
    if not places:
        return [], []
    try:
        route_legs = await provider.route(places) if len(places) > 1 else []
    except Exception as exc:
        logger.warning("route enrichment failed type=%s", type(exc).__name__)
        route_legs = []
    return places, route_legs
