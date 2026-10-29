import httpx
import pytest

from app.maps import OSMMapsProvider, build_grounded_context
from app.schemas import Place, TripRequest
from datetime import date, timedelta


@pytest.mark.asyncio
async def test_osm_search_normalizes_places():
    def handler(request):
        return httpx.Response(200, json=[{
            "osm_type": "node",
            "osm_id": 123,
            "display_name": "Lisbon, Portugal",
            "lat": "38.7223",
            "lon": "-9.1393",
            "type": "city",
        }], request=request)

    provider = OSMMapsProvider()
    provider.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await provider.search("Lisbon")
    await provider.close()

    assert result[0].id == "osm:node:123"
    assert result[0].name == "Lisbon"
    assert result[0].latitude == 38.7223


@pytest.mark.asyncio
async def test_route_failure_does_not_discard_selected_places():
    provider = OSMMapsProvider()

    async def failing_route(places):
        raise httpx.ReadTimeout("route unavailable")

    provider.route = failing_route
    places = [
        Place(id="a", name="A", latitude=1, longitude=1),
        Place(id="b", name="B", latitude=2, longitude=2),
    ]
    request = TripRequest(
        destination="A · B",
        origin=places[0],
        destinations=[places[1]],
        start_date=date.today() + timedelta(days=1),
        end_date=date.today() + timedelta(days=1),
    )
    selected, legs = await build_grounded_context(provider, request)
    await provider.close()

    assert selected == places
    assert legs == []
