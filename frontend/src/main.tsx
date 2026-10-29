import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import type { Session } from "@supabase/supabase-js";
import "./styles.css";
import { supabase, supabaseConfigured } from "./lib/supabase";
import { searchLocations } from "./lib/locations";
import {
  deleteTrip,
  listTrips,
  saveTrip,
  updateTrip,
  type Day,
  type Itinerary,
  type Place,
  type SavedTrip,
} from "./lib/trips";

const API = import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || "http://localhost:8000";
type Page = "home" | "planner" | "results";

function localDateString(date = new Date()) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Something went wrong. Please try again.";
}

async function generate(session: Session, input: {
  origin: Place | null;
  destinations: Place[];
  startDate: string;
  endDate: string;
  budget: string;
  currency: string;
  travelStyle: string;
  interests: string;
  transport: string;
  accommodation: string;
}): Promise<Itinerary> {
  const response = await fetch(`${API}/api/itineraries/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${session.access_token}` },
    body: JSON.stringify({
      destination: input.destinations.map(place => place.name).join(" · ") || input.origin?.name || "Selected destinations",
      origin: input.origin,
      destinations: input.destinations,
      start_date: input.startDate,
      end_date: input.endDate,
      budget: Number(input.budget),
      currency: input.currency,
      travelers: 1,
      interests: input.interests.split(",").map(value => value.trim()).filter(Boolean),
      pace: input.travelStyle === "slow" ? "relaxed" : input.travelStyle === "fast" ? "packed" : "balanced",
      travel_style: input.travelStyle,
      transport: input.transport,
      accommodation: input.accommodation,
    }),
  });
  if (!response.ok) {
    let detail = `Itinerary generation failed (HTTP ${response.status}).`;
    try {
      const payload = await response.json() as { detail?: { message?: string } | string };
      detail = typeof payload.detail === "string" ? payload.detail : payload.detail?.message ?? detail;
    } catch { /* use the status fallback */ }
    throw new Error(detail);
  }
  return response.json();
}

function navigate(page: Page) {
  window.location.hash = page;
}

function AuthPanel({ session, onSession }: { session: Session | null; onSession: (session: Session | null) => void }) {
  const [mode, setMode] = useState<"sign-in" | "sign-up">("sign-in");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  if (!supabaseConfigured) return <p className="config-note">Add <code>VITE_SUPABASE_URL</code> and <code>VITE_SUPABASE_PUBLISHABLE_KEY</code> to enable accounts.</p>;
  if (session) return <div className="auth-status"><span>Signed in as {session.user.email}</span><button className="text-button" onClick={() => { void supabase?.auth.signOut(); }}>Sign out</button></div>;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      if (!supabase) throw new Error("Supabase is not configured.");
      const result = mode === "sign-in"
        ? await supabase.auth.signInWithPassword({ email, password })
        : await supabase.auth.signUp({ email, password, options: { emailRedirectTo: window.location.origin } });
      if (result.error) throw result.error;
      if (mode === "sign-up" && !result.data.session) setMessage("Account created. Check your email, then sign in.");
      else onSession(result.data.session);
    } catch (submitError) { setError(errorMessage(submitError)); }
    finally { setBusy(false); }
  };

  return <form className="auth-panel" onSubmit={submit}>
    <div className="auth-tabs">
      <button type="button" className={mode === "sign-in" ? "active" : ""} onClick={() => setMode("sign-in")}>Sign in</button>
      <button type="button" className={mode === "sign-up" ? "active" : ""} onClick={() => setMode("sign-up")}>Create account</button>
    </div>
    <input aria-label="Email" type="email" required value={email} onChange={event => setEmail(event.target.value)} placeholder="Email address" />
    <input aria-label="Password" type="password" required minLength={6} value={password} onChange={event => setPassword(event.target.value)} placeholder="Password (6+ characters)" />
    <button className="primary small" disabled={busy}>{busy ? "Working…" : mode === "sign-in" ? "Sign in" : "Create account"}</button>
    {message && <p className="success">{message}</p>}{error && <p className="notice">{error}</p>}
  </form>;
}

function Shell({ session, page, children, onPage }: { session: Session; page: Page; children: React.ReactNode; onPage: (page: Page) => void }) {
  return <main>
    <nav><button className="brand-button logo" onClick={() => onPage("home")}>wayfinder<span>✦</span></button><div className="navlinks"><button className={page === "home" ? "active-link" : ""} onClick={() => onPage("home")}>Home</button><button className={page === "planner" ? "active-link" : ""} onClick={() => onPage("planner")}>Plan a trip</button><span className="user-label">{session.user.email}</span></div></nav>
    {children}
    <footer><div className="logo">wayfinder<span>✦</span></div><p>Make more room for the moments that matter.</p></footer>
  </main>;
}

function HomePage({ trips, loading, onPlan, onOpen, onDelete, session }: { trips: SavedTrip[]; loading: boolean; onPlan: () => void; onOpen: (trip: SavedTrip) => void; onDelete: (trip: SavedTrip) => void; session: Session }) {
  return <>
    <section className="hero"><div><p className="eyebrow">TRAVEL, REIMAGINED</p><h1>Go somewhere<br /><em>worth remembering.</em></h1><p className="lede">Wayfinder turns your ideas into thoughtful, data-grounded journeys with real places and routes.</p><button className="primary" onClick={onPlan}>Plan my trip <span>→</span></button></div><div className="orb"><div className="postcard">✈<small>your next chapter</small></div></div></section>
    <section className="account"><div><p className="eyebrow">YOUR WAYFINDER ACCOUNT</p><h2>Keep your journeys close.</h2><p>Signed in as {session.user.email}. Create, save and reopen private plans across sessions.</p></div><AuthPanel session={session} onSession={() => undefined} /></section>
    <section className="saved-trips"><div className="section-heading"><p className="eyebrow">YOUR SAVED TRIPS</p><h2>Return to a plan.</h2></div>{loading ? <p>Loading saved trips…</p> : trips.length === 0 ? <p className="empty-state">No saved trips yet. Start planning your next chapter.</p> : <div className="trip-list">{trips.map(trip => <article className="trip-row" key={trip.id}><button className="trip-open" onClick={() => onOpen(trip)}><strong>{trip.title}</strong><span>{trip.destination} · {trip.start_date} to {trip.end_date}</span></button><button className="delete-button" onClick={() => onDelete(trip)}>Delete</button></article>)}</div>}</section>
  </>;
}

function SearchBox({ label, value, onChange, onSelect, session }: { label: string; value: Place | null; onChange: (value: Place | null) => void; onSelect: (place: Place) => void; session: Session }) {
  const [query, setQuery] = useState(value?.name ?? "");
  const [results, setResults] = useState<Place[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (value || query.trim().length < 3) { setResults([]); return; }
    const timer = window.setTimeout(() => {
      setBusy(true);
      void searchLocations(session, query).then(setResults).catch(() => setResults([])).finally(() => setBusy(false));
    }, 350);
    return () => window.clearTimeout(timer);
  }, [query, session, value]);
  return <div className="search-field"><label>{label}<input value={query} onChange={event => { setQuery(event.target.value); onChange(null); }} placeholder="Search cities, attractions, or destinations…" /></label>{busy && <small>Searching…</small>}{results.length > 0 && <div className="suggestions">{results.map(place => <button key={place.id} onClick={() => { setQuery(place.name); setResults([]); onSelect(place); }}>{place.name}<small>{place.address}</small></button>)}</div>}</div>;
}

function PlannerPage({ session, onGenerated }: { session: Session; onGenerated: (itinerary: Itinerary) => void }) {
  const today = localDateString();
  const [origin, setOrigin] = useState<Place | null>(null);
  const [destinations, setDestinations] = useState<Place[]>([]);
  const [startDate, setStartDate] = useState(today);
  const [endDate, setEndDate] = useState(today);
  const [budget, setBudget] = useState("1800");
  const [currency, setCurrency] = useState("USD");
  const [travelStyle, setTravelStyle] = useState("balanced");
  const [interests, setInterests] = useState("food, culture");
  const [transport, setTransport] = useState("walking and public transit");
  const [accommodation, setAccommodation] = useState("comfortable and central");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const addDestination = (place: Place) => {
    if (!destinations.some(item => item.id === place.id)) setDestinations(current => [...current, place]);
  };
  const submit = async (event: React.FormEvent) => {
    event.preventDefault(); setError("");
    if (!origin || destinations.length === 0) { setError("Choose a starting location and at least one destination."); return; }
    if (endDate < startDate) { setError("End date must be on or after the start date."); return; }
    setLoading(true);
    try {
      onGenerated(await generate(session, { origin, destinations, startDate, endDate, budget, currency, travelStyle, interests, transport, accommodation }));
    } catch (submitError) { setError(errorMessage(submitError)); }
    finally { setLoading(false); }
  };
  return <section className="planner-page"><div className="section-heading"><p className="eyebrow">THE TRIP PLANNER</p><h1>Build the shape of your journey.</h1><p>Choose real places first. Wayfinder will ground the itinerary in those locations and route data.</p></div><form className="planner-form" onSubmit={submit}>
    <div className="planner-grid"><SearchBox label="Starting location" value={origin} onChange={setOrigin} onSelect={setOrigin} session={session}/><SearchBox label="Add a destination" value={null} onChange={() => undefined} onSelect={addDestination} session={session}/></div>
    {destinations.length > 0 && <div className="chips">{destinations.map((place, index) => <div className="place-chip" key={place.id}><button type="button" className="reorder" disabled={index === 0} onClick={() => setDestinations(items => { const next = [...items]; [next[index - 1], next[index]] = [next[index], next[index - 1]]; return next; })}>↑</button><span>{index + 1}. {place.name}</span><button type="button" onClick={() => setDestinations(items => items.filter(item => item.id !== place.id))}>×</button></div>)}</div>}
    <div className="form-grid planner-options"><label>From<input type="date" min={today} value={startDate} onChange={event => { setStartDate(event.target.value); if (endDate < event.target.value) setEndDate(event.target.value); }}/></label><label>To<input type="date" min={startDate} value={endDate} onChange={event => setEndDate(event.target.value)}/></label><label>Budget<input type="number" min="1" value={budget} onChange={event => setBudget(event.target.value)}/></label><label>Currency<select value={currency} onChange={event => setCurrency(event.target.value)}><option>USD</option><option>EUR</option><option>GBP</option><option>INR</option></select></label></div>
    <div className="form-grid planner-options"><label>Travel style<select value={travelStyle} onChange={event => setTravelStyle(event.target.value)}><option value="balanced">Balanced</option><option value="slow">Slow travel</option><option value="fast">Packed</option></select></label><label>Interests<input value={interests} onChange={event => setInterests(event.target.value)} placeholder="food, art, nature"/></label><label>Preferred transport<input value={transport} onChange={event => setTransport(event.target.value)}/></label><label>Accommodation<input value={accommodation} onChange={event => setAccommodation(event.target.value)}/></label></div>
    <button className="primary" disabled={loading}>{loading ? "Gathering places and planning…" : "Generate itinerary →"}</button>{error && <p className="notice">{error}</p>}
  </form></section>;
}

function RouteMap({ itinerary, selected, onSelect }: { itinerary: Itinerary; selected: Place | null; onSelect: (place: Place) => void }) {
  const googleKey = import.meta.env.VITE_GOOGLE_MAPS_API_KEY;
  if (googleKey) return <GoogleRouteMap itinerary={itinerary} selected={selected} onSelect={onSelect} apiKey={googleKey}/>;
  const stops = itinerary.stops ?? [];
  const bounds = useMemo(() => {
    const lats = stops.map(place => place.latitude); const lngs = stops.map(place => place.longitude);
    return { minLat: Math.min(...lats, 0), maxLat: Math.max(...lats, 1), minLng: Math.min(...lngs, 0), maxLng: Math.max(...lngs, 1) };
  }, [stops]);
  const point = (place: Place) => ({ x: 8 + ((place.longitude - bounds.minLng) / Math.max(bounds.maxLng - bounds.minLng, 0.01)) * 84, y: 90 - ((place.latitude - bounds.minLat) / Math.max(bounds.maxLat - bounds.minLat, 0.01)) * 80 });
  return <div className="route-map"><div className="map-label">Provider-backed route preview · {stops.length ? "OSM / OSRM" : "No coordinates returned"}</div><svg viewBox="0 0 100 100" role="img" aria-label="Interactive itinerary route map"><path className="map-grid-line" d="M0 20H100M0 50H100M0 80H100M20 0V100M50 0V100M80 0V100"/>{(itinerary.route_legs ?? []).map(leg => <polyline key={`${leg.from_place_id}-${leg.to_place_id}`} className="route-line" points={leg.geometry.map(([lat, lng]) => { const p = point({ id: "", name: "", latitude: lat, longitude: lng, category: "", provider: "" }); return `${p.x},${p.y}`; }).join(" ")}/>)}{stops.map((place, index) => { const p = point(place); return <g key={place.id} className={selected?.id === place.id ? "map-stop selected" : "map-stop"} onClick={() => onSelect(place)}><circle cx={p.x} cy={p.y} r="3.5"/><text x={p.x + 4} y={p.y + 1}>{index + 1}</text></g>; })}</svg></div>;
}

function GoogleRouteMap({ itinerary, selected, onSelect, apiKey }: { itinerary: Itinerary; selected: Place | null; onSelect: (place: Place) => void; apiKey: string }) {
  const container = useRef<HTMLDivElement>(null);
  const stops = itinerary.stops ?? [];
  useEffect(() => {
    let active = true;
    const render = () => {
      const google = (window as Window & { google?: GoogleMapsApi }).google;
      if (!active || !google || !container.current || stops.length === 0) return;
      const map = new google.maps.Map(container.current, { center: { lat: stops[0].latitude, lng: stops[0].longitude }, zoom: 7, mapTypeId: "terrain" });
      const bounds = new google.maps.LatLngBounds();
      stops.forEach((place, index) => {
        const position = { lat: place.latitude, lng: place.longitude };
        bounds.extend(position);
        const marker = new google.maps.Marker({ map, position, label: String(index + 1), title: place.name });
        marker.addListener("click", () => onSelect(place));
      });
      (itinerary.route_legs ?? []).forEach(leg => new google.maps.Polyline({ map, path: leg.geometry.map(([lat, lng]) => ({ lat, lng })), strokeColor: "#115e59", strokeWeight: 4 }));
      if (stops.length > 1) map.fitBounds(bounds);
    };
    if ((window as Window & { google?: GoogleMapsApi }).google) render();
    else {
      const script = document.createElement("script");
      script.src = `https://maps.googleapis.com/maps/api/js?key=${encodeURIComponent(apiKey)}`;
      script.async = true; script.onload = render; script.onerror = () => undefined;
      document.head.appendChild(script);
    }
    return () => { active = false; };
  }, [apiKey, itinerary, onSelect, stops]);
  return <div className="route-map google-route-map"><div className="map-label">Google Maps · provider-backed route</div><div ref={container} className="google-map-container"/>{selected && <button className="map-selected-note" onClick={() => onSelect(selected)}>Selected: {selected.name}</button>}</div>;
}

function DayView({ day, index }: { day: Day; index: number }) {
  return <article className="day"><div className="day-number">{String(index + 1).padStart(2, "0")}</div><div><p className="date">{new Date(`${day.date}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" })}</p><h3>{day.title}</h3><p>{day.summary}</p>{day.activities.map(activity => <div className="activity" key={activity.time + activity.title}><b>{activity.time}</b><span><strong>{activity.title}</strong>{activity.description}</span><small>${activity.estimated_cost}</small></div>)}</div></article>;
}

function ResultsPage({ itinerary, session, onSaved }: { itinerary: Itinerary; session: Session; onSaved: (trip: SavedTrip) => void }) {
  const [selected, setSelected] = useState<Place | null>(itinerary.stops?.[0] ?? null);
  const [title, setTitle] = useState(`${itinerary.destination} getaway`);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const save = async () => {
    try {
      const trip = await saveTrip(session, { title, destination: itinerary.destination, start_date: itinerary.start_date, end_date: itinerary.end_date, travelers: 1, budget: itinerary.budget ?? 1800, currency: itinerary.currency ?? "USD", preferences: { interests: [], pace: "balanced" }, itinerary });
      onSaved(trip); setMessage("Trip saved to your account.");
    } catch (saveError) { setError(errorMessage(saveError)); }
  };
  return <section className="results-page"><div className="results-heading"><div><p className="eyebrow">YOUR GENERATED ITINERARY</p><h1>{itinerary.destination}</h1><p className="lede">{itinerary.summary || `${itinerary.days.length} days, grounded in selected places and route data.`}</p></div><div className="save-controls"><input value={title} onChange={event => setTitle(event.target.value)} aria-label="Trip title"/><button className="primary small" onClick={() => void save()}>Save trip</button></div></div><div className="results-grid"><RouteMap itinerary={itinerary} selected={selected} onSelect={setSelected}/><aside className="place-panel">{selected ? <><p className="eyebrow">SELECTED PLACE</p><h2>{selected.name}</h2><p>{selected.address || selected.category}</p><p className="muted">Coordinates: {selected.latitude.toFixed(4)}, {selected.longitude.toFixed(4)}</p>{selected.source_url && <a href={selected.source_url} target="_blank" rel="noreferrer">Open source</a>}<a href={`https://www.google.com/maps/search/?api=1&query=${selected.latitude},${selected.longitude}`} target="_blank" rel="noreferrer">Open in Google Maps</a><a href={`https://www.google.com/search?q=${encodeURIComponent(selected.name)}`} target="_blank" rel="noreferrer">Search on Google</a></> : <p>Select a stop on the map.</p>}</aside></div><div className="results-meta"><span>Estimated cost: {itinerary.currency ?? "USD"} {itinerary.total_estimated_cost}</span><span>{(itinerary.route_legs ?? []).reduce((total, leg) => total + leg.distance_km, 0).toFixed(1)} km routed</span></div><div className="days">{itinerary.days.map((day, index) => <DayView day={day} index={index} key={day.date}/>)}</div>{message && <p className="success">{message}</p>}{error && <p className="notice">{error}</p>}{itinerary.images?.length ? <div className="image-gallery">{itinerary.images.map(image => <figure key={image.source_url}><img src={image.url} alt={image.alt} loading="lazy"/><figcaption>Photo by <a href={image.photographer_url} target="_blank" rel="noreferrer">{image.photographer_name}</a> on <a href={image.source_url} target="_blank" rel="noreferrer">Unsplash</a></figcaption></figure>)}</div> : null}</section>;
}

function App() {
  const [page, setPage] = useState<Page>((window.location.hash.slice(1) as Page) || "home");
  const [session, setSession] = useState<Session | null>(null);
  const [authLoading, setAuthLoading] = useState(supabaseConfigured);
  const [trips, setTrips] = useState<SavedTrip[]>([]);
  const [tripsLoading, setTripsLoading] = useState(false);
  const [itinerary, setItinerary] = useState<Itinerary | null>(null);
  useEffect(() => {
    const onHash = () => setPage((window.location.hash.slice(1) as Page) || "home");
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);
  useEffect(() => {
    if (!supabase) { setAuthLoading(false); return; }
    let active = true;
    void supabase.auth.getSession().then(({ data }) => { if (active) { setSession(data.session); setAuthLoading(false); } });
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => { setSession(nextSession); setAuthLoading(false); });
    return () => { active = false; data.subscription.unsubscribe(); };
  }, []);
  useEffect(() => {
    if (!session) { setTrips([]); setItinerary(null); return; }
    setTripsLoading(true); void listTrips(session).then(setTrips).catch(() => undefined).finally(() => setTripsLoading(false));
  }, [session]);
  if (authLoading) return <main><section className="auth-gate"><p>Checking your secure session…</p></section></main>;
  if (!session) return <main><section className="auth-gate"><div><p className="eyebrow">WAYFINDER</p><h1>Plan somewhere<br/><em>worth remembering.</em></h1><p className="lede">Sign in to create and save private travel plans.</p></div><AuthPanel session={null} onSession={setSession}/></section></main>;
  const onPage = (next: Page) => navigate(next);
  const openTrip = (trip: SavedTrip) => { setItinerary(trip.itinerary); navigate("results"); };
  const deleteSavedTrip = async (trip: SavedTrip) => { if (!window.confirm(`Delete "${trip.title}"?`)) return; await deleteTrip(session, trip.id); setTrips(items => items.filter(item => item.id !== trip.id)); };
  return <Shell session={session} page={page} onPage={onPage}>{page === "home" && <HomePage session={session} trips={trips} loading={tripsLoading} onPlan={() => onPage("planner")} onOpen={openTrip} onDelete={trip => void deleteSavedTrip(trip)}/>} {page === "planner" && <PlannerPage session={session} onGenerated={result => { setItinerary(result); onPage("results"); }}/>} {page === "results" && itinerary && <ResultsPage itinerary={itinerary} session={session} onSaved={trip => setTrips(items => [trip, ...items.filter(item => item.id !== trip.id)])}/>}</Shell>;
}

createRoot(document.getElementById("root")!).render(<React.StrictMode><App/></React.StrictMode>);
