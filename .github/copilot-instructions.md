# Copilot instructions

- Keep the backend provider-agnostic: depend on `AIProvider` and `MapsProvider`, not vendor SDKs in route handlers.
- Preserve demo mode and deterministic tests; tests must never call external APIs.
- Validate generated itinerary candidates for dates, costs, and required trip fields before returning them.
- Never add Gemini dependencies or APIs. Groq is configured through `GROQ_MODEL`.
- Keep secrets in environment variables and maintain owner-only Supabase RLS.
