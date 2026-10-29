import logging

import httpx

from .config import Settings
from .schemas import Itinerary, ItineraryImage

logger = logging.getLogger(__name__)


class UnsplashProvider:
    def __init__(self, settings: Settings):
        self.access_key = settings.unsplash_access_key
        self.client = httpx.AsyncClient(timeout=8.0)

    async def close(self) -> None:
        await self.client.aclose()

    async def enrich(self, itinerary: Itinerary) -> Itinerary:
        if not self.access_key:
            return itinerary
        query = itinerary.destination
        try:
            response = await self.client.get(
                "https://api.unsplash.com/search/photos",
                params={"query": query, "per_page": 5, "orientation": "landscape"},
                headers={"Authorization": f"Client-ID {self.access_key}"},
            )
            response.raise_for_status()
            payload = response.json()
            results = payload.get("results", []) if isinstance(payload, dict) else []
            images = []
            for item in results[:5] if isinstance(results, list) else []:
                if not isinstance(item, dict):
                    continue
                urls = item.get("urls") or {}
                user = item.get("user") or {}
                links = item.get("links") or {}
                regular_url = urls.get("regular")
                photographer_name = user.get("name")
                photographer_url = (user.get("links") or {}).get("html")
                source_url = links.get("html")
                if not all(isinstance(value, str) and value for value in (regular_url, photographer_name, photographer_url, source_url)):
                    continue
                images.append(ItineraryImage(
                    url=regular_url,
                    alt=item.get("alt_description") or f"Travel photo of {itinerary.destination}",
                    photographer_name=photographer_name,
                    photographer_url=photographer_url,
                    source_url=source_url,
                ))
            itinerary.images = images
        except Exception as exc:
            logger.warning("unsplash enrichment failed destination=%s detail=%s", itinerary.destination, str(exc)[:300])
        return itinerary
