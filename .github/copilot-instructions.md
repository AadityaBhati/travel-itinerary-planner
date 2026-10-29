# Copilot instructions

- Keep the backend provider-agnostic: depend on `AIProvider` and `MapsProvider`, not vendor SDKs in route handlers.
- Preserve demo mode and deterministic tests; tests must never call external APIs.
- Validate generated itinerary candidates for dates, costs, and required trip fields before returning them.
- Use Azure OpenAI through the backend-only `AZURE_OPENAI_*` settings; never expose provider keys in frontend variables.
- Keep secrets in environment variables and maintain owner-only Supabase RLS.
