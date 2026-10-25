# Wayfinder travel itinerary planner

Wayfinder is a production-minded MVP scaffold for building private travel itineraries with a React/Vite/TypeScript client and a FastAPI/Pydantic API. Authentication is required for the application and generation API. Demo mode uses deterministic local data; production mode uses Azure OpenAI.

## Quick start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000` and Swagger at `/docs`.

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

Set `VITE_API_BASE_URL` to the backend URL when it is not `http://localhost:8000`. For authentication and persistence, also set `VITE_SUPABASE_URL` and `VITE_SUPABASE_PUBLISHABLE_KEY` in `frontend/.env`. Only the Supabase publishable key belongs in the frontend.

## Configuration

Production mode is the default (`DEMO_MODE=false`) and requires `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_API_KEY`, and the exact Azure deployment name in `AZURE_OPENAI_DEPLOYMENT_NAME`. The endpoint should be your Azure OpenAI resource endpoint or its `/openai/v1` equivalent; the backend normalizes the path. Set `DEMO_MODE=true` only for deterministic local development or tests. Keep the Azure key and optional `UNSPLASH_ACCESS_KEY` server-side in `backend/.env`; incomplete production configuration fails clearly instead of falling back to mock data.

Run backend tests with `cd backend; pytest`. Frontend checks use `npm run build`.

Apply both `supabase/migrations/001_create_trips.sql` and `supabase/migrations/002_extend_trips_for_persistence.sql` in the Supabase SQL editor or with the Supabase CLI. The second migration adds persistence fields, an authenticated-user owner default, update timestamps, grants, and explicit owner-only RLS policies. In Supabase Auth settings, enable Email provider and set `http://localhost:5173` as the site URL/redirect URL for local confirmation links. The frontend requires a Supabase session before showing the trip builder, and the backend validates the bearer token on generation endpoints.

With Supabase configured, users can sign up, sign in, save generated itineraries, reload saved trips, update saved records, and delete them. Supabase authentication is required before the builder or generation API is available; without configuration, the app shows a clear setup message. The frontend queries only the signed-in user's rows; RLS remains the database authorization boundary.
![Top Language](https://img.shields.io/github/languages/top/AadityaBhati/travel-itinerary-planner)
