from datetime import date
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator


class TripRequest(BaseModel):
    destination: str = Field(min_length=2, max_length=120)
    start_date: date
    end_date: date
    travelers: int = Field(default=1, ge=1, le=20)
    budget: Decimal = Field(default=2500, gt=0, le=1_000_000)
    interests: list[str] = Field(default_factory=list, max_length=12)
    pace: Literal["relaxed", "balanced", "packed"] = "balanced"

    @field_validator("destination")
    @classmethod
    def clean_destination(cls, value: str) -> str:
        return " ".join(value.split())

    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        if (self.end_date - self.start_date).days > 30:
            raise ValueError("trip length cannot exceed 31 days")
        return self

    @property
    def days(self) -> int:
        return (self.end_date - self.start_date).days + 1


class Activity(BaseModel):
    time: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=120)
    description: str = Field(min_length=1, max_length=500)
    category: Literal["food", "culture", "nature", "stay", "transport", "other"] = "other"
    estimated_cost: Decimal = Field(default=0, ge=0)


class ItineraryDay(BaseModel):
    date: date
    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=500)
    activities: list[Activity] = Field(min_length=1, max_length=20)
    estimated_cost: Decimal = Field(ge=0)

    @model_validator(mode="after")
    def cost_matches_activities(self):
        total = sum((activity.estimated_cost for activity in self.activities), Decimal(0))
        if abs(total - self.estimated_cost) > Decimal("0.01"):
            raise ValueError("day estimated_cost must equal activity costs")
        return self


class Itinerary(BaseModel):
    destination: str
    start_date: date
    end_date: date
    total_estimated_cost: Decimal = Field(ge=0)
    days: list[ItineraryDay] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def validate_semantics(self):
        expected = (self.end_date - self.start_date).days + 1
        if len(self.days) != expected:
            raise ValueError("itinerary must contain one day per trip date")
        expected_dates = [self.start_date.fromordinal(self.start_date.toordinal() + i) for i in range(expected)]
        if [day.date for day in self.days] != expected_dates:
            raise ValueError("itinerary dates must be consecutive")
        total = sum((day.estimated_cost for day in self.days), Decimal(0))
        if abs(total - self.total_estimated_cost) > Decimal("0.01"):
            raise ValueError("total_estimated_cost must equal day costs")
        return self


class RegenerateDayRequest(BaseModel):
    trip: TripRequest
    date: date
    current_day: ItineraryDay | None = None

    @model_validator(mode="after")
    def date_in_trip(self):
        if not self.trip.start_date <= self.date <= self.trip.end_date:
            raise ValueError("date must be within trip range")
        return self
