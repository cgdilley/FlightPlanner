from __future__ import annotations

from SprelfJSON import JSONModel

from datetime import date
from typing import Iterable, Iterator
import itertools

from Data import SeatType
from Data.FlightSearch import FlightSearch, SearchFilter, LegSearch, Passengers


class LegOptions(JSONModel):
    origins: list[str]
    destinations: list[str]
    dates: list[date]

    @classmethod
    def date_range(cls, start: date, end: date) -> Iterable[date]:
        d = start
        while d <= end:
            yield d
            d += date.resolution

    def __iter__(self) -> Iterator[LegSearch]:
        return iter(self.build_legs())

    def build_legs(self) -> Iterable[LegSearch]:
        for origin, destination, d in itertools.product(self.origins, self.destinations, self.dates):
            yield LegSearch(origin=origin, destination=destination, date=d)


# class FlightOptions(JSONModel):
##     searches: list[FlightSearch]
#     passengers: Passengers
#     filters: list[SearchFilter] = []
#
#     def __iter__(self) -> Iterator[FlightSearch]:
#         return iter(self.searches)
#
#     def add_legs(self, *legs: LegOptions) -> Self:
#         combos: Iterable[tuple[LegSearch, ...]] = itertools.product(*legs)
#         searches = (FlightSearch(legs=list(combo), passengers=self.passengers, filters=self.filters)
#                     for combo in combos)
#         self.searches.extend(searches)
#         return self
#
#     @classmethod
#     def build(cls, *legs: LegOptions,
#               passengers: Passengers,
#               filters: list[SearchFilter] | None = None) -> FlightOptions:
#         if not filters:
#             filters = []
#         return FlightOptions(searches=[], passengers=passengers, filters=filters) \
#             .add_legs(*legs)


class FlightOptions(JSONModel):
    name: str
    legs: list[LegOptions]
    passengers: Passengers
    currency: str
    filters: list[SearchFilter] = []
    seat: SeatType = SeatType.Economy

    def __iter__(self) -> Iterator[FlightSearch]:
        return iter(self.build_searches())

    def build_searches(self) -> Iterable[FlightSearch]:
        combos: Iterable[tuple[LegSearch, ...]] = itertools.product(*self.legs)
        for combo in combos:
            yield FlightSearch(legs=list(combo),
                               passengers=self.passengers,
                               filters=self.filters,
                               currency=self.currency,
                               seat=self.seat)
