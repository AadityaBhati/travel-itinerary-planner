import type { Session } from "@supabase/supabase-js";
import type { Place } from "./trips";

const API = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "http://localhost:8000";

export async function searchLocations(session: Session, query: string): Promise<Place[]> {
  const response = await fetch(`${API}/api/locations/search?q=${encodeURIComponent(query)}`, {
    headers: { Authorization: `Bearer ${session.access_token}` },
  });
  if (!response.ok) throw new Error("Location search is temporarily unavailable.");
  const payload = await response.json() as { results?: Place[] };
  return payload.results ?? [];
}
