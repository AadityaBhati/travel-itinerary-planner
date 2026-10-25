import type { Session } from "@supabase/supabase-js";
import { supabase } from "./supabase";

export type Activity = {
  time: string;
  title: string;
  description: string;
  category: string;
  estimated_cost: number;
};

export type Day = {
  date: string;
  title: string;
  summary: string;
  activities: Activity[];
  estimated_cost: number;
};

export type Itinerary = {
  destination: string;
  start_date: string;
  end_date: string;
  total_estimated_cost: number;
  days: Day[];
};

export type TripPreferences = {
  interests: string[];
  pace: "relaxed" | "balanced" | "packed";
};

export type SavedTrip = {
  id: string;
  owner_id: string;
  title: string;
  destination: string;
  start_date: string;
  end_date: string;
  travelers: number;
  budget: number;
  currency: string;
  preferences: TripPreferences;
  itinerary: Itinerary;
  created_at: string;
  updated_at: string;
};

export function tripInsertPayload(input: Omit<SavedTrip, "id" | "owner_id" | "created_at" | "updated_at">) {
  return {
    title: input.title,
    destination: input.destination,
    start_date: input.start_date,
    end_date: input.end_date,
    travelers: input.travelers,
    budget: input.budget,
    currency: input.currency,
    preferences: input.preferences,
    itinerary: input.itinerary,
  };
}

function requireClient() {
  if (!supabase) {
    throw new Error("Supabase is not configured. Add VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY.");
  }
  return supabase;
}

export async function listTrips(session: Session): Promise<SavedTrip[]> {
  const { data, error } = await requireClient()
    .from("trips")
    .select("*")
    .eq("owner_id", session.user.id)
    .order("updated_at", { ascending: false });
  if (error) throw error;
  return (data ?? []) as SavedTrip[];
}

export async function saveTrip(
  _session: Session,
  input: Omit<SavedTrip, "id" | "owner_id" | "created_at" | "updated_at">,
): Promise<SavedTrip> {
  const { data, error } = await requireClient()
    .from("trips")
    .insert(tripInsertPayload(input))
    .select()
    .single();
  if (error) throw error;
  return data as SavedTrip;
}

export async function updateTrip(
  session: Session,
  id: string,
  input: Partial<Pick<SavedTrip, "title" | "itinerary" | "destination" | "start_date" | "end_date" | "travelers" | "budget" | "currency" | "preferences">>,
): Promise<SavedTrip> {
  const { data, error } = await requireClient()
    .from("trips")
    .update(input)
    .eq("id", id)
    .eq("owner_id", session.user.id)
    .select()
    .single();
  if (error) throw error;
  return data as SavedTrip;
}

export async function deleteTrip(session: Session, id: string): Promise<void> {
  const { error } = await requireClient()
    .from("trips")
    .delete()
    .eq("id", id)
    .eq("owner_id", session.user.id);
  if (error) throw error;
}
