from contextlib import asynccontextmanager
import logging
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .config import Settings, get_settings
from .providers import AIProvider, AIProviderError, build_provider
from .schemas import Itinerary, ItineraryDay, RegenerateDayRequest, TripRequest

@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.provider = build_provider(get_settings())
    yield


app = FastAPI(title="Wayfinder API", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger(__name__)


app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    if not hasattr(app.state, "provider"):
        app.state.provider = build_provider(settings)
    return app.state.provider


@app.get("/health")
async def health():
    return {"status": "ok", "demo_mode": get_settings().demo_mode}


@app.post("/api/itineraries/generate", response_model=Itinerary)
async def generate(request: TripRequest, ai: AIProvider = Depends(provider)):
    try:
        return await ai.generate(request)
    except AIProviderError as exc:
        logger.warning("generate request failed code=%s", exc.error_code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.error_code, "message": str(exc)}) from exc


@app.post("/api/itineraries/regenerate-day", response_model=ItineraryDay)
async def regenerate_day(request: RegenerateDayRequest, ai: AIProvider = Depends(provider)):
    try:
        return await ai.regenerate_day(request)
    except AIProviderError as exc:
        logger.warning("regenerate-day request failed code=%s", exc.error_code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.error_code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
