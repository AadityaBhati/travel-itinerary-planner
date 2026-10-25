# Wayfinder travel itinerary planner

Wayfinder is a production-minded MVP scaffold for building travel itineraries with a React/Vite/TypeScript client and a FastAPI/Pydantic API. It runs without credentials in demo mode, while keeping provider interfaces ready for Supabase and Groq.

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

The backend defaults to deterministic mock providers (`DEMO_MODE=true`). Set `DEMO_MODE=false`, `GROQ_API_KEY`, and optionally `GROQ_MODEL` (default `openai/gpt-oss-20b`) to use Groq via `AsyncGroq`. Keep `GROQ_API_KEY` server-side in `backend/.env`; never use it in a `VITE_*` variable. No Gemini integration is used.

Run backend tests with `cd backend; pytest`. Frontend checks use `npm run build`.

Apply both `supabase/migrations/001_create_trips.sql` and `supabase/migrations/002_extend_trips_for_persistence.sql` in the Supabase SQL editor or with the Supabase CLI. The second migration adds persistence fields, an authenticated-user owner default, update timestamps, grants, and explicit owner-only RLS policies. In Supabase Auth settings, enable Email provider and set `http://localhost:5173` as the site URL/redirect URL for local confirmation links.

With Supabase configured, users can sign up, sign in, save generated itineraries, reload saved trips, update saved records, and delete them. Without Supabase configuration, demo generation remains available but account and persistence controls show a configuration message. The frontend queries only the signed-in user's rows; RLS remains the database authorization boundary.
