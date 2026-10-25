from datetime import date, timedelta

from fastapi.testclient import TestClient
from app.main import app
from app.main import get_current_user
from app.providers import AIProvider, AIProviderError, MockAIProvider

client = TestClient(app)
app.dependency_overrides[get_current_user] = lambda: type("User", (), {"id": "test-user", "email": "test@example.com"})()
from app.main import provider
app.dependency_overrides[provider] = lambda: MockAIProvider()


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_demo_itinerary():
    start = date.today() + timedelta(days=1)
    response = client.post("/api/itineraries/generate", json={"destination": "Lisbon", "start_date": start.isoformat(), "end_date": (start + timedelta(days=1)).isoformat(), "budget": 900, "interests": ["food"]})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["days"]) == 2
    assert payload["days"][0]["date"] == start.isoformat()


def test_rejects_invalid_dates():
    start = date.today() + timedelta(days=3)
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": start.isoformat(), "end_date": (start - timedelta(days=2)).isoformat()})
    assert response.status_code == 422


def test_rejects_past_dates():
    past = date.today() - timedelta(days=1)
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": past.isoformat(), "end_date": past.isoformat()})
    assert response.status_code == 422


def test_generation_requires_authentication():
    auth_override = app.dependency_overrides.pop(get_current_user)
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": (date.today() + timedelta(days=1)).isoformat(), "end_date": (date.today() + timedelta(days=1)).isoformat()})
    app.dependency_overrides[get_current_user] = auth_override
    assert response.status_code == 401


class FailingProvider(AIProvider):
    async def generate(self, request):
        raise AIProviderError("Azure OpenAI rate limit or quota exceeded. Try again later.", status_code=429, error_code="azure_rate_limit")

    async def regenerate_day(self, request):
        raise AIProviderError("Azure OpenAI rate limit or quota exceeded. Try again later.", status_code=429, error_code="azure_rate_limit")


def test_generation_provider_errors_are_safe_and_classified():
    app.dependency_overrides[provider] = lambda: FailingProvider()
    travel_date = (date.today() + timedelta(days=1)).isoformat()
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": travel_date, "end_date": travel_date})
    app.dependency_overrides[provider] = lambda: MockAIProvider()
    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": "azure_rate_limit",
            "message": "Azure OpenAI rate limit or quota exceeded. Try again later.",
        }
    }
