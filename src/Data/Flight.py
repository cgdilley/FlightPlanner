from __future__ import annotations

from SprelfJSON import JSONModel, JSONObject, ModelElem

from datetime import timedelta, datetime, date
from typing import Iterator
import itertools

from Data.Enums import SeatType, JourneyType


#


class Layover(JSONModel):
    location: str
    start_time: datetime
    end_time: datetime

    @property
    def duration(self) -> timedelta:
        return self.end_time - self.start_time


#


class Ticket(JSONModel):
    price: float
    currency: str
    checked_bags: int
    carryon_bags: int
    seat_type: SeatType


#


class Hop(JSONModel):
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    airline: str
    tickets: list[Ticket]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if len(self.tickets) == 0:
            raise ValueError("Flight must have at least one ticket")
        if not all(t.currency == self.tickets[0].currency for t in self.tickets):
            raise ValueError("Tickets must all have the same currency")
        self.tickets = sorted(self.tickets, key=lambda t: t.price)

    @property
    def duration(self) -> timedelta:
        return self.arrival_time - self.departure_time

    @property
    def currency(self) -> str:
        return self.tickets[0].currency

    def cheapest(self) -> Ticket:
        return self.tickets[0]

    def ticket(self, seat_type: SeatType) -> Ticket | None:
        for t in self.tickets:
            if t.seat_type.value >= seat_type.value:
                return t
        return None


#


class Flight(JSONModel):
    hops: list[Hop]
    info: dict = dict()

    class _Details(JSONModel):
        origin: str
        destination: str
        departure_time: datetime
        arrival_time: datetime
        duration: str
        cheapest: float
        currency: str
        stops: tuple[str, ...]

    def __init__(self, **kwargs):
        _ = kwargs.pop("details", None)
        super().__init__(**kwargs)
        for hop1, hop2 in itertools.pairwise(self.hops):
            # if hop1.destination != hop2.origin:
            #     raise ValueError("Flight legs don't connect")
            if hop1.currency != hop2.currency:
                raise ValueError("Flight legs have different ticket currencies")

    def to_json(self, **kwargs) -> JSONObject:
        j = super().to_json(**kwargs)
        j["details"] = Flight._Details(origin=self.origin,
                                       destination=self.destination,
                                       departure_time=self.departure_time,
                                       arrival_time=self.arrival_time,
                                       duration=self.duration_str,
                                       cheapest=self.cheapest(),
                                       currency=self.currency,
                                       stops=self.stops()).to_json()
        return j

    def __iter__(self) -> Iterator[Hop]:
        return iter(self.hops)

    @property
    def origin(self) -> str:
        return self.hops[0].origin

    @property
    def destination(self) -> str:
        return self.hops[-1].destination

    @property
    def departure_time(self) -> datetime:
        return self.hops[0].departure_time

    @property
    def arrival_time(self) -> datetime:
        return self.hops[-1].arrival_time

    @property
    def duration(self) -> timedelta:
        return self.arrival_time - self.departure_time

    @property
    def duration_str(self) -> str:
        d = self.duration
        return f"{int(d.total_seconds() // 3600)}h{int((d.total_seconds() % 3600) // 60):02d}"

    @property
    def currency(self) -> str:
        return self.hops[0].currency

    @property
    def layovers(self) -> list[Layover]:
        return [Layover(location=hop2.origin,
                        start_time=hop1.arrival_time,
                        end_time=hop2.departure_time)
                for hop1, hop2 in itertools.pairwise(self.hops)]

    @property
    def layover_time(self) -> timedelta:
        return sum((lo.duration for lo in self.layovers), timedelta(minutes=0))

    @property
    def in_air_time(self) -> timedelta:
        return self.duration - self.layover_time

    def cheapest_tickets(self) -> list[Ticket]:
        return [hop.cheapest() for hop in self.hops]

    def cheapest(self) -> float:
        return sum(t.price for t in self.cheapest_tickets())

    def tickets(self, seat_type: SeatType) -> list[Ticket]:
        return [hop.ticket(seat_type) for hop in self.hops]

    def seats(self) -> list[SeatType]:
        return list({hop.cheapest().seat_type for hop in self.hops})

    def stops(self) -> tuple[str, ...]:
        stops = tuple()
        for hop in self.hops:
            if len(stops) == 0 or stops[-1] != hop.origin:
                stops += (hop.origin,)
            stops += (hop.destination,)
        return stops


#


class Trip(JSONModel):
    flights: list[Flight]

    class _Details(JSONModel):
        currency: str
        journey: JourneyType
        cheapest: float
        depart_date: date
        return_date: date
        route: str
        airlines: set[str]

    def __init__(self, **kwargs):
        _ = kwargs.pop("details", None)
        super().__init__(**kwargs)
        if len(self.flights) == 0:
            raise ValueError("Trip must have at least one flight")
        if not all(f1.currency == f2.currency for f1, f2 in itertools.pairwise(self.flights)):
            raise ValueError("Flights must all have the same currency")

    def to_json(self, **kwargs) -> JSONObject:
        j = super().to_json(**kwargs)
        j["details"] = Trip._Details(currency=self.currency,
                                     journey=self.journey,
                                     cheapest=self.cheapest(),
                                     depart_date=self.flights[0].departure_time.date(),
                                     return_date=self.flights[-1].departure_time.date(),
                                     route=" | ".join("->".join(stops) for stops in self.route()),
                                     airlines={h.airline for f in self.flights for h in f.hops}).to_json()
        return j

    def __iter__(self) -> Iterator[Flight]:
        return iter(self.flights)

    @property
    def journey(self) -> JourneyType:
        return JourneyType.infer(*((flight.origin, flight.destination) for flight in self.flights))

    @property
    def currency(self) -> str:
        return self.flights[0].currency

    def cheapest(self) -> float:
        return sum(f.cheapest() for f in self.flights)

    def route(self) -> tuple[tuple[str, ...], ...]:
        return tuple(f.stops() for f in self.flights)
