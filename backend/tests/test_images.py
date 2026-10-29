from datetime import date, timedelta

import httpx
import pytest

from app.config import Settings
from app.images import UnsplashProvider
from app.schemas import Itinerary, ItineraryDay
from decimal import Decimal


def itinerary():
    travel_date = date.today() + timedelta(days=1)
    return Itinerary(
        destination="Lisbon",
        start_date=travel_date,
        end_date=travel_date,
        total_estimated_cost=Decimal("10"),
        days=[ItineraryDay(
            date=travel_date,
            title="A day",
            summary="A plan",
            estimated_cost=Decimal("10"),
            activities=[{
                "time": "09:00",
                "title": "Walk",
                "description": "A morning walk",
                "category": "culture",
                "estimated_cost": Decimal("10"),
            }],
        )],
    )


def provider_with_response(payload=None, status_code=200, error=None):
    def handler(request):
        if error:
            raise error
        return httpx.Response(status_code, json=payload, request=request)

    provider = UnsplashProvider(Settings(unsplash_access_key="test-key"))
    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return provider


@pytest.mark.asyncio
async def test_unsplash_maps_image_and_attribution_metadata():
    provider = provider_with_response({"results": [{
        "urls": {"regular": "https://images.example/lisbon.jpg"},
        "alt_description": "Lisbon rooftops",
        "user": {"name": "Jane Doe", "links": {"html": "https://unsplash.com/@jane"}},
        "links": {"html": "https://unsplash.com/photos/lisbon"},
    }]})
    result = await provider.enrich(itinerary())
    await provider.close()

    assert result.images[0].url == "https://images.example/lisbon.jpg"
    assert result.images[0].alt == "Lisbon rooftops"
    assert result.images[0].photographer_name == "Jane Doe"
    assert result.images[0].photographer_url == "https://unsplash.com/@jane"
    assert result.images[0].source_url == "https://unsplash.com/photos/lisbon"


@pytest.mark.asyncio
async def test_unsplash_empty_results_return_no_images():
    provider = provider_with_response({"results": []})
    result = await provider.enrich(itinerary())
    await provider.close()
    assert result.images == []


@pytest.mark.asyncio
async def test_unsplash_malformed_items_are_skipped_without_failing():
    provider = provider_with_response({"results": [{"urls": {}}, "not-an-object"]})
    result = await provider.enrich(itinerary())
    await provider.close()
    assert result.images == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "error",
    [
        httpx.ReadTimeout("timed out"),
        None,
    ],
)
async def test_unsplash_failures_leave_itinerary_usable(error):
    provider = provider_with_response({"error": "denied"} if error is None else None, 403 if error is None else 200, error=error)
    result = await provider.enrich(itinerary())
    await provider.close()
    assert result.destination == "Lisbon"
    assert result.images == []


@pytest.mark.asyncio
async def test_unsplash_missing_credentials_skips_request():
    called = False

    def handler(request):
        nonlocal called
        called = True
        return httpx.Response(200, json={"results": []}, request=request)

    provider = UnsplashProvider(Settings())
    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await provider.enrich(itinerary())
    await provider.close()

    assert result.images == []
    assert called is False
