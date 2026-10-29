import { describe, expect, it } from "vitest";
import { tripInsertPayload, type Itinerary } from "./trips";

const itinerary: Itinerary = {
  destination: "Lisbon",
  start_date: "2026-06-01",
  end_date: "2026-06-01",
  total_estimated_cost: 10,
  images: [{
    url: "https://images.example/lisbon.jpg",
    alt: "Lisbon rooftops",
    photographer_name: "Jane Doe",
    photographer_url: "https://unsplash.com/@jane",
    source_url: "https://unsplash.com/photos/lisbon",
  }],
  days: [{
    date: "2026-06-01",
    title: "A day out",
    summary: "A simple plan.",
    estimated_cost: 10,
    activities: [{
      time: "09:00",
      title: "Walk",
      description: "A morning walk.",
      category: "nature",
      estimated_cost: 10,
    }],
  }],
};

describe("trip persistence payload", () => {
  it("preserves the complete itinerary and excludes ownership metadata", () => {
    const payload = tripInsertPayload({
      title: "Lisbon getaway",
      destination: "Lisbon",
      start_date: "2026-06-01",
      end_date: "2026-06-01",
      travelers: 2,
      budget: 1800,
      currency: "USD",
      preferences: { interests: ["food"], pace: "balanced" },
      itinerary,
    });

    expect(payload.itinerary).toEqual(itinerary);
    expect(payload).not.toHaveProperty("owner_id");
    expect(payload).not.toHaveProperty("id");
  });
});
