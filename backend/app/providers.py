import json
import logging
from abc import ABC, abstractmethod
from datetime import timedelta
from decimal import Decimal
from groq import (
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    AsyncGroq,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from .config import Settings
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


class MapsProvider(ABC):
    @abstractmethod
    async def geocode(self, destination: str) -> dict[str, float | str]: ...


class MockMapsProvider(MapsProvider):
    async def geocode(self, destination: str) -> dict[str, float | str]:
        return {"destination": destination, "latitude": 0.0, "longitude": 0.0}


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


class GroqAIProvider(AIProvider):
    def __init__(self, settings: Settings):
        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when demo mode is disabled")
        self.client = AsyncGroq(api_key=settings.groq_api_key, timeout=60.0, max_retries=1)
        self.model = settings.groq_model

    @staticmethod
    def _schema(properties: dict) -> dict:
        return {
            "type": "object",
            "properties": properties,
            "required": list(properties),
            "additionalProperties": False,
        }

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
            status_code, code, message = 502, "groq_authentication_error", "Groq authentication failed. Check the backend API key."
        elif isinstance(error, BadRequestError):
            status_code, code, message = 502, "groq_invalid_request", "Groq rejected the itinerary request. Check the configured model and structured response format."
        elif isinstance(error, RateLimitError):
            status_code, code, message = 429, "groq_rate_limit", "Groq rate limit or quota exceeded. Try again later."
        elif isinstance(error, APITimeoutError):
            status_code, code, message = 504, "groq_timeout", "Groq did not respond in time. Try again."
        elif isinstance(error, APIConnectionError):
            status_code, code, message = 502, "groq_connection_error", "The backend could not connect to Groq."
        elif isinstance(error, APIStatusError):
            status_code, code, message = 502, "groq_api_error", f"Groq returned an upstream error (HTTP {error.status_code})."
        elif isinstance(error, (json.JSONDecodeError, TypeError, KeyError)):
            status_code, code, message = 502, "groq_invalid_response", "Groq returned an invalid itinerary response."
        else:
            status_code, code, message = 502, "ai_provider_error", "Itinerary generation failed in the AI provider."
        logger.error("itinerary generation failed operation=%s code=%s detail=%s", operation, code, str(error)[:500])
        return AIProviderError(message, status_code=status_code, error_code=code)

    async def _complete(self, prompt: str, schema: dict, operation: str) -> dict:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                temperature=0.2,
                max_completion_tokens=8192,
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "wayfinder_itinerary", "strict": True, "schema": schema},
                },
                messages=[
                    {"role": "system", "content": "Return only JSON matching the supplied schema. Do not include markdown."},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("Groq returned an empty response")
            return json.loads(content)
        except AIProviderError:
            raise
        except Exception as error:
            raise self._error(error, operation) from error

    async def generate(self, request: TripRequest) -> Itinerary:
        prompt = f"Create a {request.days}-day itinerary for {request.destination}. Dates {request.start_date} to {request.end_date}, {request.travelers} travelers, budget {request.budget}, interests {request.interests}, pace {request.pace}. Return fields destination,start_date,end_date,total_estimated_cost,days; each day has date,title,summary,activities and estimated_cost; each activity has time,title,description,category,estimated_cost."
        try:
            return Itinerary.model_validate(await self._complete(prompt, self._itinerary_schema(), "generate"))
        except AIProviderError:
            raise
        except Exception as error:
            raise self._error(error, "generate_validation") from error

    async def regenerate_day(self, request: RegenerateDayRequest) -> ItineraryDay:
        prompt = f"Create one itinerary day for {request.trip.destination} on {request.date}, budget-aware and aligned to {request.trip.interests}. Return title,summary,activities,estimated_cost."
        try:
            return ItineraryDay.model_validate(await self._complete(prompt, self._day_schema(), "regenerate_day") | {"date": request.date})
        except AIProviderError:
            raise
        except Exception as error:
            raise self._error(error, "regenerate_day_validation") from error


def build_provider(settings: Settings) -> AIProvider:
    return MockAIProvider() if settings.demo_mode else GroqAIProvider(settings)
