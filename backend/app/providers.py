import json
import logging
from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import Decimal

from openai import (
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from .config import Settings
from .images import UnsplashProvider
from .schemas import Activity, Itinerary, ItineraryDay, RegenerateDayRequest, TripRequest

logger = logging.getLogger(__name__)


class AIProviderError(Exception):
    def __init__(self, message: str, *, status_code: int = 502, error_code: str = "ai_provider_error"):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code


class AIProvider(ABC):
    @abstractmethod
    async def generate(self, request: TripRequest) -> Itinerary: ...

    @abstractmethod
    async def regenerate_day(self, request: RegenerateDayRequest) -> ItineraryDay: ...


class MockAIProvider(AIProvider):
    def _day(self, request: TripRequest, day_date, index: int) -> ItineraryDay:
        activities = [
            Activity(time="09:00", title=f"Walk through {request.destination}", description="A relaxed orientation walk with neighborhood highlights.", category="culture", estimated_cost=Decimal("18")),
            Activity(time="13:00", title="Local lunch", description="A hand-picked local meal with time to recharge.", category="food", estimated_cost=Decimal("28")),
            Activity(time="17:00", title="Golden hour viewpoint", description="Finish the day with a scenic, unhurried view.", category="nature", estimated_cost=Decimal("12")),
        ]
        return ItineraryDay(date=day_date, title=f"Day {index}: Find your bearings", summary=f"An easy first look at {request.destination}.", activities=activities, estimated_cost=sum((a.estimated_cost for a in activities), Decimal(0)))

    async def generate(self, request: TripRequest) -> Itinerary:
        days = [self._day(request, request.start_date + timedelta(days=i), i + 1) for i in range(request.days)]
        return Itinerary(destination=request.destination, start_date=request.start_date, end_date=request.end_date, total_estimated_cost=sum((day.estimated_cost for day in days), Decimal(0)), days=days)

    async def regenerate_day(self, request: RegenerateDayRequest) -> ItineraryDay:
        return self._day(request.trip, request.date, (request.date - request.trip.start_date).days + 1)


class AzureOpenAIProvider(AIProvider):
    def __init__(self, settings: Settings):
        missing = [
            name for name, value in (
                ("AZURE_OPENAI_ENDPOINT", settings.azure_openai_endpoint),
                ("AZURE_OPENAI_API_KEY", settings.azure_openai_api_key),
                ("AZURE_OPENAI_DEPLOYMENT_NAME", settings.azure_openai_deployment_name),
            ) if not value
        ]
        if missing:
            raise ValueError(f"Missing required production configuration: {', '.join(missing)}")
        self.client = AsyncOpenAI(
            api_key=settings.azure_openai_api_key,
            base_url=normalize_azure_base_url(settings.azure_openai_endpoint),
            timeout=60.0,
            max_retries=1,
        )
        self.model = settings.azure_openai_deployment_name

    async def close(self) -> None:
        await self.client.close()

    @staticmethod
    def _schema(properties: dict) -> dict:
        return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}

    @classmethod
    def _itinerary_schema(cls) -> dict:
        activity = cls._schema({
            "time": {"type": "string"},
            "title": {"type": "string"},
            "description": {"type": "string"},
            "category": {"type": "string", "enum": ["food", "culture", "nature", "stay", "transport", "other"]},
            "estimated_cost": {"type": "number", "minimum": 0},
        })
        day = cls._schema({
            "date": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "activities": {"type": "array", "items": activity, "minItems": 1, "maxItems": 20},
            "estimated_cost": {"type": "number", "minimum": 0},
        })
        return cls._schema({
            "destination": {"type": "string"},
            "start_date": {"type": "string"},
            "end_date": {"type": "string"},
            "total_estimated_cost": {"type": "number", "minimum": 0},
            "days": {"type": "array", "items": day, "minItems": 1, "maxItems": 31},
            "images": {"type": "array", "items": cls._schema({
                "url": {"type": "string"},
                "alt": {"type": "string"},
                "photographer_name": {"type": "string"},
                "photographer_url": {"type": "string"},
                "source_url": {"type": "string"},
            }), "maxItems": 0},
        })

    @classmethod
    def _day_schema(cls) -> dict:
        activity = cls._itinerary_schema()["properties"]["days"]["items"]["properties"]["activities"]["items"]
        return cls._schema({
            "date": {"type": "string"},
            "title": {"type": "string"},
            "summary": {"type": "string"},
            "activities": {"type": "array", "items": activity, "minItems": 1, "maxItems": 20},
            "estimated_cost": {"type": "number", "minimum": 0},
        })

    def _error(self, error: Exception, operation: str) -> AIProviderError:
        if isinstance(error, AuthenticationError):
            code, status, message = "azure_authentication_error", 502, "Azure OpenAI authentication failed. Check the backend deployment key."
        elif isinstance(error, BadRequestError):
            code, status, message = "azure_invalid_request", 502, "Azure OpenAI rejected the itinerary request. Check the deployment and response format."
        elif isinstance(error, RateLimitError):
            code, status, message = "azure_rate_limit", 429, "Azure OpenAI rate limit or quota exceeded. Try again later."
        elif isinstance(error, APITimeoutError):
            code, status, message = "azure_timeout", 504, "Azure OpenAI did not respond in time. Try again."
        elif isinstance(error, APIConnectionError):
            code, status, message = "azure_connection_error", 502, "The backend could not connect to Azure OpenAI."
        elif isinstance(error, APIStatusError):
            code, status, message = "azure_api_error", 502, f"Azure OpenAI returned an upstream error (HTTP {error.status_code})."
        elif isinstance(error, (json.JSONDecodeError, TypeError, KeyError, ValueError)):
            code, status, message = "azure_invalid_response", 502, "Azure OpenAI returned an invalid itinerary response."
        else:
            code, status, message = "ai_provider_error", 502, "Itinerary generation failed in the AI provider."
        logger.error("itinerary generation failed operation=%s code=%s detail=%s", operation, code, str(error)[:500])
        return AIProviderError(message, status_code=status, error_code=code)

    async def _complete(self, prompt: str, schema: dict, operation: str) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                max_completion_tokens=8192,
                response_format={"type": "json_schema", "json_schema": {"name": "wayfinder_itinerary", "strict": True, "schema": schema}},
                messages=[
                    {"role": "system", "content": "Return only JSON matching the supplied schema. Do not include markdown."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Azure OpenAI returned an empty response")
            return json.loads(content)
        except Exception as error:
            if isinstance(error, AIProviderError):
                raise
            raise self._error(error, operation) from error

    async def generate(self, request: TripRequest) -> Itinerary:
        prompt = f"Create a {request.days}-day itinerary for {request.destination}. Dates {request.start_date} to {request.end_date}, {request.travelers} travelers, budget {request.budget}, interests {request.interests}, pace {request.pace}. Return destination, dates, days, activities, and calculated costs. Leave images empty; images are added by the server."
        try:
            itinerary = Itinerary.model_validate(await self._complete(prompt, self._itinerary_schema(), "generate"))
            if (itinerary.destination != request.destination
                    or itinerary.start_date != request.start_date
                    or itinerary.end_date != request.end_date):
                raise ValueError("Azure OpenAI returned itinerary fields that do not match the request")
            return itinerary
        except AIProviderError:
            raise
        except Exception as error:
            raise self._error(error, "generate_validation") from error

    async def regenerate_day(self, request: RegenerateDayRequest) -> ItineraryDay:
        prompt = f"Create one itinerary day for {request.trip.destination} on {request.date}, aligned to {request.trip.interests}. Return title, summary, activities, and calculated estimated_cost."
        try:
            return ItineraryDay.model_validate(await self._complete(prompt, self._day_schema(), "regenerate_day") | {"date": request.date})
        except AIProviderError:
            raise
        except Exception as error:
            raise self._error(error, "regenerate_day_validation") from error


def build_provider(settings: Settings) -> AIProvider:
    base_provider = MockAIProvider() if settings.demo_mode else AzureOpenAIProvider(settings)
    if settings.unsplash_access_key:
        return ImageEnrichedAIProvider(base_provider, UnsplashProvider(settings))
    return base_provider


def normalize_azure_base_url(endpoint: str) -> str:
    normalized = endpoint.rstrip("/")
    if not normalized.endswith("/openai/v1"):
        normalized = f"{normalized}/openai/v1"
    return f"{normalized}/"


class ImageEnrichedAIProvider(AIProvider):
    def __init__(self, provider: AIProvider, images: UnsplashProvider):
        self.provider = provider
        self.images = images

    async def close(self) -> None:
        close = getattr(self.provider, "close", None)
        if close:
            await close()
        await self.images.close()

    async def generate(self, request: TripRequest) -> Itinerary:
        return await self.images.enrich(await self.provider.generate(request))

    async def regenerate_day(self, request: RegenerateDayRequest) -> ItineraryDay:
        return await self.provider.regenerate_day(request)
