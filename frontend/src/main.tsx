import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Session } from "@supabase/supabase-js";
import "./styles.css";
import { supabase, supabaseConfigured } from "./lib/supabase";
import { deleteTrip, listTrips, saveTrip, updateTrip, type Day, type Itinerary, type SavedTrip } from "./lib/trips";

const API = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "http://localhost:8000";
async function generate(destination: string, startDate: string, endDate: string): Promise<Itinerary> {
  const response = await fetch(`${API}/api/itineraries/generate`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ destination, start_date: startDate, end_date: endDate, travelers: 2, budget: 1800, interests: ["food", "culture"], pace: "balanced" }),
  });
  if (!response.ok) {
    let detail = `Itinerary generation failed (HTTP ${response.status}).`;
    try {
      const payload = await response.json() as { detail?: { message?: string } | string };
      if (typeof payload.detail === "string") detail = payload.detail;
      else if (payload.detail?.message) detail = payload.detail.message;
    } catch {
      // Keep the status-based message when the server does not return JSON.
    }
    throw new Error(detail);
  }
  return response.json();
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

function AuthPanel({ session, onSession }: { session: Session | null; onSession: (session: Session | null) => void }) {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  if (!supabaseConfigured) return <p className="config-note">Account and persistence features need <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> in <code>frontend/.env</code>.</p>;
  if (session) return <div className="auth-status"><span>Signed in as {session.user.email}</span><button className="text-button" onClick={() => { void supabase?.auth.signOut(); }}>Sign out</button></div>;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(""); setMessage("");
    try {
      if (!supabase) throw new Error("Supabase is not configured.");
      const result = mode === "sign-in"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } });
      if (result.error) throw result.error;
      if (mode === "sign-up" && !result.data.session) setMessage("Account created. Check your email to confirm your address, then sign in.");
      else onSession(result.data.session);
    } catch (submitError) { setError(errorMessage(submitError)); } finally { setBusy(false); }
  };

  return <form className="auth-panel" onSubmit={submit}>
    <div className="auth-tabs"><button type="button" className={mode === "sign-in" ? "active" : ""} onClick={() => setMode("sign-in")}>Sign in</button><button type="button" className={mode === "sign-up" ? "active" : ""} onClick={() => setMode("sign-up")}>Create account</button></div>
    <input aria-label="Email" type="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="Email address" />
    <input aria-label="Password" type="password" required minLength={6} value={password} onChange={event => setPassword(event.target.value)} placeholder="Password (6+ characters)" />
    <button className="primary small" disabled={busy}>{busy ? "Working…" : mode === "sign-in" ? "Sign in" : "Create account"}</button>
    {message && <p className="success">{message}</p>}{error && <p className="notice">{error}</p>}
  </form>;
}

function DayView({ day, index }: { day: Day; index: number }) {
  return <article className="day"><div className="day-number">{String(index + 1).padStart(2, "0")}</div><div><p className="date">{new Date(`${day.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</p><h3>{day.title}</h3><p>{day.summary}</p>{day.activities.map(activity => <div className="activity" key={activity.time + activity.title}><b>{activity.time}</b><span><strong>{activity.title}</strong>{activity.description}</span><small>${activity.estimated_cost}</small></div>)}</div></article>;
}

function ItineraryView({ itinerary, savedTrip, session, onSaved }: { itinerary: Itinerary; savedTrip: SavedTrip | null; session: Session | null; onSaved: (trip: SavedTrip) => void }) {
  const [saving, setSaving] = useState(false); const [message, setMessage] = useState(""); const [error, setError] = useState("");
  const [title, setTitle] = useState(savedTrip?.title ?? `${itinerary.destination} getaway`);
  const persist = async () => {
    if (!session) { setError("Sign in before saving an itinerary."); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const input = { title: title.trim() || `${itinerary.destination} getaway`, destination: itinerary.destination, start_date: itinerary.start_date, end_date: itinerary.end_date, travelers: savedTrip?.travelers ?? 2, budget: savedTrip?.budget ?? 1800, currency: savedTrip?.currency ?? "USD", preferences: savedTrip?.preferences ?? { interests: ["food", "culture"], pace: "balanced" as const }, itinerary };
      const trip = savedTrip ? await updateTrip(session, savedTrip.id, input) : await saveTrip(session, input);
      onSaved(trip); setMessage(savedTrip ? "Trip updated." : "Trip saved to your account.");
    } catch (persistError) { setError(errorMessage(persistError)); } finally { setSaving(false); }
  };
  return <section className="itinerary">
    <div className="section-heading"><p className="eyebrow">YOUR ITINERARY</p><h2>{itinerary.destination}, thoughtfully planned.</h2><p>{itinerary.days.length} days · Estimated ${itinerary.total_estimated_cost}</p></div>
    <div className="save-bar"><label className="title-field">Trip title<input value={title} onChange={event => setTitle(event.target.value)} /></label><span>{savedTrip ? "Saved itinerary" : session ? "This itinerary is not saved yet." : "Sign in to save this itinerary."}</span><button className="primary small" disabled={saving || !session} onClick={() => void persist()}>{saving ? "Saving…" : savedTrip ? "Save changes" : "Save trip"}</button></div>
    {message && <p className="success">{message}</p>}{error && <p className="notice">{error}</p>}
    <div className="days">{itinerary.days.map((day, i) => <DayView day={day} index={i} key={day.date} />)}</div>
  </section>;
}

function App() {
  const [destination, setDestination] = useState("Lisbon"); const [start, setStart] = useState("2026-06-01"); const [end, setEnd] = useState("2026-06-03");
  const [itinerary, setItinerary] = useState<Itinerary | null>(null); const [savedTrip, setSavedTrip] = useState<SavedTrip | null>(null); const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [session, setSession] = useState<Session | null>(null); const [authLoading, setAuthLoading] = useState(supabaseConfigured); const [tripsLoading, setTripsLoading] = useState(false); const [loading, setLoading] = useState(false); const [error, setError] = useState("");

  useEffect(() => {
    if (!supabase) { setAuthLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); setAuthLoading(false); } });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => { setSession(nextSession); setAuthLoading(false); });
    return () => { active = false; data.subscription.unsubscribe(); };
  }, []);

  useEffect(() => {
    if (!session) { setTrips([]); return; }
    setTripsLoading(true); void listTrips(session).then(setTrips).catch(loadError => setError(errorMessage(loadError))).finally(() => setTripsLoading(false));
  }, [session]);

  const create = async () => {
    setLoading(true); setError(""); setSavedTrip(null);
    try { setItinerary(await generate(destination, start, end)); }
    catch (generationError) { setItinerary(null); setError(errorMessage(generationError)); }
    finally { setLoading(false); }
  };

  const openTrip = (trip: SavedTrip) => { setSavedTrip(trip); setItinerary(trip.itinerary); setDestination(trip.destination); setStart(trip.start_date); setEnd(trip.end_date); document.getElementById("itinerary")?.scrollIntoView({ behavior: "smooth" }); };
  const removeTrip = async (trip: SavedTrip) => {
    if (!session || !window.confirm(`Delete "${trip.title}"? This cannot be undone.`)) return;
    try { await deleteTrip(session, trip.id); setTrips(current => current.filter(item => item.id !== trip.id)); if (savedTrip?.id === trip.id) { setSavedTrip(null); setItinerary(null); } }
    catch (deleteError) { setError(errorMessage(deleteError)); }
  };

  return <main>
    <nav><div className="logo">wayfinder<span>✦</span></div><div className="navlinks"><a href="#saved-trips">My trips</a><a href="#builder">Plan</a><span className="user-label">{authLoading ? "Loading…" : session?.user.email ?? "Guest"}</span></div></nav>
    <section className="hero"><div><p className="eyebrow">TRAVEL, REIMAGINED</p><h1>Go somewhere<br /><em>worth remembering.</em></h1><p className="lede">Wayfinder turns your big ideas into thoughtful, beautifully-paced journeys.</p><button className="primary" onClick={() => document.getElementById("builder")?.scrollIntoView({ behavior: "smooth" })}>Plan a new trip <span>→</span></button></div><div className="orb"><div className="postcard">✈<small>your next chapter</small></div></div></section>
    <section className="account"><div><p className="eyebrow">YOUR WAYFINDER ACCOUNT</p><h2>Keep your journeys close.</h2><p>Sign in to save and reopen plans across sessions. Demo generation remains available without an account.</p></div><AuthPanel session={session} onSession={setSession} /></section>
    <section id="builder" className="builder"><div className="section-heading"><p className="eyebrow">THE TRIP BUILDER</p><h2>Where will you go?</h2><p>Tell us the shape of your trip. We'll fill in the rest.</p></div><div className="form-grid"><label>Destination<input value={destination} onChange={e => setDestination(e.target.value)} placeholder="e.g. Kyoto, Japan" /></label><label>From<input type="date" value={start} onChange={e => setStart(e.target.value)} /></label><label>To<input type="date" value={end} onChange={e => setEnd(e.target.value)} /></label></div><button className="primary" disabled={loading} onClick={() => void create()}>{loading ? "Finding your way…" : "Create my itinerary →"}</button>{error && <p className="notice">{error}</p>}</section>
    {session && <section id="saved-trips" className="saved-trips"><div className="section-heading"><p className="eyebrow">YOUR SAVED TRIPS</p><h2>Return to a plan.</h2></div>{tripsLoading ? <p>Loading saved trips…</p> : trips.length === 0 ? <p className="empty-state">No saved trips yet. Generate one and save it above.</p> : <div className="trip-list">{trips.map(trip => <article className="trip-row" key={trip.id}><button className="trip-open" onClick={() => openTrip(trip)}><strong>{trip.title}</strong><span>{trip.destination} · {trip.start_date} to {trip.end_date}</span></button><button className="delete-button" onClick={() => void removeTrip(trip)}>Delete</button></article>)}</div>}</section>}
    {itinerary && <div id="itinerary"><ItineraryView key={savedTrip?.id ?? `${itinerary.destination}-${itinerary.start_date}`} itinerary={itinerary} savedTrip={savedTrip} session={session} onSaved={trip => { setSavedTrip(trip); setTrips(current => [trip, ...current.filter(item => item.id !== trip.id)]); }} /></div>}
    <footer><div className="logo">wayfinder<span>✦</span></div><p>Make more room for the moments that matter.</p></footer>
  </main>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App /></React.StrictMode>);
