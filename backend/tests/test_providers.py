import json

import pytest
import httpx
from groq import AuthenticationError, RateLimitError

from app.config import Settings
from app.providers import GroqAIProvider
from app.schemas import TripRequest


class FakeCompletions:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.kwargs = None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, completions):
        self.chat = type("Chat", (), {"completions": completions})()


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeResponse:
    def __init__(self, content):
        self.choices = [type("Choice", (), {"message": FakeMessage(content)})()]


def valid_payload():
    return {
        "destination": "Rome",
        "start_date": "2026-06-01",
        "end_date": "2026-06-01",
        "total_estimated_cost": 10,
        "days": [{
            "date": "2026-06-01",
            "title": "A day in Rome",
            "summary": "A compact plan.",
            "estimated_cost": 10,
            "activities": [{
                "time": "09:00",
                "title": "Walk",
                "description": "A morning walk.",
                "category": "culture",
                "estimated_cost": 10,
            }],
        }],
    }


@pytest.mark.asyncio
async def test_groq_generation_uses_strict_json_schema():
    completions = FakeCompletions(FakeResponse(json.dumps(valid_payload())))
    provider = GroqAIProvider(Settings(groq_api_key="test-key", demo_mode=False))
    provider.client = FakeClient(completions)

    result = await provider.generate(TripRequest(destination="Rome", start_date="2026-06-01", end_date="2026-06-01"))

    assert result.destination == "Rome"
    response_format = completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False


@pytest.mark.asyncio
async def test_invalid_groq_itinerary_output_is_rejected():
    provider = GroqAIProvider(Settings(groq_api_key="test-key", demo_mode=False))
    provider.client = FakeClient(FakeCompletions(FakeResponse("{}")))

    with pytest.raises(Exception) as raised:
        await provider.generate(TripRequest(destination="Rome", start_date="2026-06-01", end_date="2026-06-01"))

    assert raised.value.error_code == "ai_provider_error"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (AuthenticationError("bad key", response=httpx.Response(401, request=httpx.Request("POST", "https://api.groq.com")), body={}), 502, "groq_authentication_error"),
        (RateLimitError("limited", response=httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com")), body={}), 429, "groq_rate_limit"),
    ],
)
async def test_groq_errors_are_classified(error, status_code, error_code):
    provider = GroqAIProvider(Settings(groq_api_key="test-key", demo_mode=False))
    provider.client = FakeClient(FakeCompletions(error=error))

    with pytest.raises(Exception) as raised:
        await provider.generate(TripRequest(destination="Rome", start_date="2026-06-01", end_date="2026-06-01"))

    assert raised.value.status_code == status_code
    assert raised.value.error_code == error_code
