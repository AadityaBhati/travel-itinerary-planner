from contextlib import asynccontextmanager
import inspect
import logging
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .auth import AuthenticatedUser, get_current_user
from .config import Settings, get_settings
from .maps import MapsProvider, build_grounded_context, build_maps_provider
from .providers import AIProvider, AIProviderError, build_provider
from .schemas import Itinerary, ItineraryDay, RegenerateDayRequest, TripRequest

@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.provider = build_provider(get_settings())
    application.state.maps = build_maps_provider(get_settings())
    try:
        yield
    finally:
        close = getattr(application.state.provider, "close", None)
        if close:
            await close()
        await application.state.maps.close()


app = FastAPI(title="Wayfinder API", version="0.1.0", lifespan=lifespan)
logger = logging.getLogger(__name__)


app.add_middleware(CORSMiddleware, allow_origins=[get_settings().frontend_origin], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])


def provider(settings: Settings = Depends(get_settings)) -> AIProvider:
    if not hasattr(app.state, "provider"):
        app.state.provider = build_provider(settings)
    return app.state.provider


def maps_provider(settings: Settings = Depends(get_settings)) -> MapsProvider:
    if not hasattr(app.state, "maps"):
        app.state.maps = build_maps_provider(settings)
    return app.state.maps


async def generate_with_context(ai: AIProvider, request: TripRequest, context: dict):
    if "context" in inspect.signature(ai.generate).parameters:
        return await ai.generate(request, context)
    return await ai.generate(request)


@app.get("/health")
async def health():
    settings = get_settings()
    return {"status": "ok", "demo_mode": settings.demo_mode, "maps_provider": settings.maps_provider}


@app.get("/api/locations/search")
async def search_locations(
    q: str,
    _user: AuthenticatedUser = Depends(get_current_user),
    maps: MapsProvider = Depends(maps_provider),
):
    try:
        return {"results": await maps.search(q)}
    except Exception as exc:
        logger.warning("location search failed type=%s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Location search is temporarily unavailable.") from exc


@app.post("/api/itineraries/generate", response_model=Itinerary)
async def generate(request: TripRequest, _user: AuthenticatedUser = Depends(get_current_user), ai: AIProvider = Depends(provider), maps: MapsProvider = Depends(maps_provider)):
    try:
        places, route_legs = await build_grounded_context(maps, request)
        context = {"places": [place.model_dump() for place in places], "route_legs": [leg.model_dump() for leg in route_legs]}
        return await generate_with_context(ai, request, context)
    except HTTPException:
        raise
    except AIProviderError as exc:
        logger.warning("generate request failed code=%s", exc.error_code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.error_code, "message": str(exc)}) from exc


@app.post("/api/itineraries/regenerate-day", response_model=ItineraryDay)
async def regenerate_day(request: RegenerateDayRequest, _user: AuthenticatedUser = Depends(get_current_user), ai: AIProvider = Depends(provider)):
    try:
        return await ai.regenerate_day(request)
    except AIProviderError as exc:
        logger.warning("regenerate-day request failed code=%s", exc.error_code)
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.error_code, "message": str(exc)}) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
