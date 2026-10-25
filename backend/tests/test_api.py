from fastapi.testclient import TestClient
from app.main import app
from app.providers import AIProvider, AIProviderError

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_generate_demo_itinerary():
    response = client.post("/api/itineraries/generate", json={"destination": "Lisbon", "start_date": "2026-06-01", "end_date": "2026-06-02", "budget": 900, "interests": ["food"]})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["days"]) == 2
    assert payload["days"][0]["date"] == "2026-06-01"


def test_rejects_invalid_dates():
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": "2026-06-03", "end_date": "2026-06-01"})
    assert response.status_code == 422


class FailingProvider(AIProvider):
    async def generate(self, request):
        raise AIProviderError("Groq rate limit or quota exceeded. Try again later.", status_code=429, error_code="groq_rate_limit")

    async def regenerate_day(self, request):
        raise AIProviderError("Groq rate limit or quota exceeded. Try again later.", status_code=429, error_code="groq_rate_limit")


def test_generation_provider_errors_are_safe_and_classified():
    from app.main import provider

    app.dependency_overrides[provider] = lambda: FailingProvider()
    response = client.post("/api/itineraries/generate", json={"destination": "Rome", "start_date": "2026-06-01", "end_date": "2026-06-01"})
    app.dependency_overrides.clear()
    assert response.status_code == 429
    assert response.json() == {
        "detail": {
            "code": "groq_rate_limit",
            "message": "Groq rate limit or quota exceeded. Try again later.",
        }
    }
