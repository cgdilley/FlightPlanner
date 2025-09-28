from __future__ import annotations

from SprelfJSON import JSONModel, ModelElem

from datetime import time, date
from abc import ABC, abstractmethod
from typing import Iterable

from Data.Enums import JourneyType, SeatType
from Data.Flight import Flight


#


class Passengers(JSONModel):
    adults: int
    children: int = 0
    infants_in_seat: int = 0
    infants_on_lap: int = 0

    def __hash__(self) -> int:
        return hash((self.adults, self.children, self.infants_in_seat, self.infants_on_lap))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Passengers):
            return False
        return (self.adults, self.children, self.infants_in_seat, self.infants_on_lap) == \
               (other.adults, other.children, other.infants_in_seat, other.infants_on_lap)


class LegSearch(JSONModel):
    origin: str
    destination: str
    date: date



#


class SearchFilter(JSONModel, ABC):

    @abstractmethod
    def filter(self, flight: Flight) -> bool:
        ...


#


class FlightSearch(JSONModel):
    # journey: JourneyType
    legs: list[LegSearch]
    passengers: Passengers
    currency: str
    seat: SeatType = SeatType.Economy
    filters: list[SearchFilter] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if len(self.legs) == 0:
            raise ValueError("Flight must have at least one leg")
        # if self.journey == JourneyType.OneWay and len(self.legs) > 1:
        #     raise ValueError("One-way flights must have exactly one leg")
        # elif self.journey == JourneyType.RoundTrip and len(self.legs) != 2:
        #     raise ValueError("Round-trip flights must have exactly two legs")
        # elif self.journey == JourneyType.MultiLeg:
        #     if len(self.legs) < 2:
        #         raise ValueError("Multi-leg flights must have at least two legs")
        #     # if self.legs[0].origin != self.legs[-1].destination:
        #     #     raise ValueError("First and last leg must have the same origin and destination")

    @property
    def journey(self) -> JourneyType:
        return JourneyType.infer(*((leg.origin, leg.destination) for leg in self.legs))

    @property
    def origin(self) -> str:
        return self.legs[0].origin

    @property
    def destination(self) -> str:
        return self.legs[-1].destination

    def iter_stops(self) -> Iterable[str]:
        for i, leg in enumerate(self.legs):
            if i == 0 or leg.origin != self.legs[i - 1].destination:
                yield leg.origin
            yield leg.destination

    def iter_dates(self) -> Iterable[date]:
        yield from (leg.date for leg in self.legs)

    def has_filter(self, filter_type: type[SearchFilter]) -> bool:
        return any(isinstance(f, filter_type) for f in self.filters)

    def get_filter(self, filter_type: type[SearchFilter]) -> SearchFilter | None:
        for f in self.filters:
            if isinstance(f, filter_type):
                return f
        return None


class StopsSearchFilter(SearchFilter):
    stops: int

    def filter(self, flight: Flight) -> bool:
        return len(flight.layovers) <= self.stops


class LuggageSearchFilter(SearchFilter):
    checked: int
    carryon: int = 1

    def filter(self, flight: Flight) -> bool:
        for leg in flight.hops:
            leg.tickets = [t for t in leg.tickets
                           if t.checked_bags >= self.checked and t.carryon_bags >= self.carryon]
            if len(leg.tickets) == 0:
                return False
        return True


class PriceSearchFilter(SearchFilter):
    max: float
    min: float = 0
    currency: str = "EUR"

    def filter(self, flight: Flight) -> bool:
        if self.currency != flight.currency:
            raise ValueError(f"Currency mismatch: {self.currency} != {flight.currency}")
        return self.min <= sum(c.price for c in flight.cheapest_tickets()) <= self.max


class DepartureTimeSearchFilter(SearchFilter):
    min: time
    max: time

    def filter(self, flight: Flight) -> bool:
        return self.min <= flight.departure_time.time() <= self.max


class ArrivalTimeSearchFilter(SearchFilter):
    min: time
    max: time

    def filter(self, flight: Flight) -> bool:
        return self.min <= flight.arrival_time.time() <= self.max


class DurationSearchFilter(SearchFilter):
    max: int  # minutes
    min: int = 0  # minutes

    def filter(self, flight: Flight) -> bool:
        return self.min <= flight.duration.total_seconds() // 60 <= self.max
