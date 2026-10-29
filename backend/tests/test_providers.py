import json
from datetime import date, timedelta

import pytest
import httpx
from openai import AuthenticationError, RateLimitError

from app.config import Settings
from app.providers import AzureOpenAIProvider, MockAIProvider, build_provider, normalize_azure_base_url
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
    travel_date = (date.today() + timedelta(days=1)).isoformat()
    return {
        "destination": "Rome",
        "start_date": travel_date,
        "end_date": travel_date,
        "total_estimated_cost": 10,
        "days": [{
            "date": travel_date,
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
async def test_azure_generation_uses_strict_json_schema():
    completions = FakeCompletions(FakeResponse(json.dumps(valid_payload())))
    provider = AzureOpenAIProvider(Settings(azure_openai_api_key="test-key", azure_openai_endpoint="https://example.openai.azure.com", azure_openai_deployment_name="test-deployment", demo_mode=False))
    provider.client = FakeClient(completions)

    travel_date = date.today() + timedelta(days=1)
    result = await provider.generate(TripRequest(destination="Rome", start_date=travel_date, end_date=travel_date))

    assert result.destination == "Rome"
    response_format = completions.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert response_format["json_schema"]["schema"]["additionalProperties"] is False


@pytest.mark.parametrize(
    ("endpoint", "expected"),
    [
        ("https://example.openai.azure.com", "https://example.openai.azure.com/openai/v1/"),
        ("https://example.openai.azure.com/", "https://example.openai.azure.com/openai/v1/"),
        ("https://example.openai.azure.com/openai/v1", "https://example.openai.azure.com/openai/v1/"),
        ("https://example.openai.azure.com/openai/v1/", "https://example.openai.azure.com/openai/v1/"),
    ],
)
def test_azure_endpoint_normalization(endpoint, expected):
    assert normalize_azure_base_url(endpoint) == expected


def test_azure_uses_configured_deployment_name():
    provider = AzureOpenAIProvider(Settings(
        azure_openai_api_key="test-key",
        azure_openai_endpoint="https://example.openai.azure.com",
        azure_openai_deployment_name="wayfinder-prod",
        demo_mode=False,
    ))
    assert provider.model == "wayfinder-prod"
    assert str(provider.client.base_url) == "https://example.openai.azure.com/openai/v1/"


def test_production_provider_requires_explicit_configuration():
    with pytest.raises(ValueError, match="AZURE_OPENAI_ENDPOINT"):
        build_provider(Settings(
            _env_file=None,
            demo_mode=False,
            azure_openai_endpoint=None,
            azure_openai_api_key=None,
            azure_openai_deployment_name="",
        ))


def test_mock_provider_requires_explicit_demo_mode():
    provider = build_provider(Settings(_env_file=None, demo_mode=True))
    assert isinstance(provider, MockAIProvider)


@pytest.mark.asyncio
async def test_invalid_azure_itinerary_output_is_rejected():
    provider = AzureOpenAIProvider(Settings(azure_openai_api_key="test-key", azure_openai_endpoint="https://example.openai.azure.com", azure_openai_deployment_name="test-deployment", demo_mode=False))
    provider.client = FakeClient(FakeCompletions(FakeResponse("{}")))

    with pytest.raises(Exception) as raised:
        await provider.generate(TripRequest(destination="Rome", start_date=date.today() + timedelta(days=1), end_date=date.today() + timedelta(days=1)))

    assert raised.value.error_code == "azure_invalid_response"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code", "error_code"),
    [
        (AuthenticationError("bad key", response=httpx.Response(401, request=httpx.Request("POST", "https://example.openai.azure.com")), body={}), 502, "azure_authentication_error"),
        (RateLimitError("limited", response=httpx.Response(429, request=httpx.Request("POST", "https://example.openai.azure.com")), body={}), 429, "azure_rate_limit"),
    ],
)
async def test_azure_errors_are_classified(error, status_code, error_code):
    provider = AzureOpenAIProvider(Settings(azure_openai_api_key="test-key", azure_openai_endpoint="https://example.openai.azure.com", azure_openai_deployment_name="test-deployment", demo_mode=False))
    provider.client = FakeClient(FakeCompletions(error=error))

    with pytest.raises(Exception) as raised:
        await provider.generate(TripRequest(destination="Rome", start_date=date.today() + timedelta(days=1), end_date=date.today() + timedelta(days=1)))

    assert raised.value.status_code == status_code
    assert raised.value.error_code == error_code
