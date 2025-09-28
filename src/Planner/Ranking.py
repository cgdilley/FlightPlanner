from __future__ import annotations

from SprelfJSON import JSONModel
from abc import ABC, abstractmethod
from typing import Iterable, Callable, Collection
from datetime import datetime, date, time, timedelta

from Planner.Query import QueryResult, ScoredQueryResult, ScoreInfo
from Data.Flight import Flight, Trip


class Ranker(JSONModel, ABC):

    def rank(self, results: Iterable[QueryResult]) -> list[ScoredQueryResult]:
        results = list(self._score(list(results)))
        return [
            ScoredQueryResult(query=qr, score=s, rank=i)
            for i, (qr, s) in enumerate(sorted(results, key=lambda x: x[1], reverse=True))]

    @abstractmethod
    def _score(self, flights: Iterable[QueryResult]) -> list[tuple[QueryResult, ScoreInfo]]:
        ...


#


class RankProperty(JSONModel, ABC):
    weight: float = 1
    inverted: bool = False

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._range: tuple[float | None, float | None] = (None, None)

    def __hash__(self) -> int:
        return hash(type(self).__name__)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, type(self))

    def apply(self, flight: Flight, **kwargs) -> float:
        v = self._apply(flight, **kwargs)
        if self.inverted:
            v *= -1
        if self._range[0] is None or v < self._range[0]:
            self._range = (v, self._range[1])
        elif self._range[1] is None or v > self._range[1]:
            self._range = (self._range[0], v)
        return v

    @abstractmethod
    def _apply(self, flight: Flight, **kwargs) -> float:
        ...

    def normalize(self, value: float, **kwargs) -> float:
        if self._range[0] is None or self._range[1] is None:
            return value
        if self._range[0] == self._range[1]:
            return 0
        return (value - self._range[0]) / (self._range[1] - self._range[0])

    def reset(self):
        self._range = (None, None)


#


class StandardRanker(Ranker):
    properties: set[RankProperty] = set()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if len(self.properties) == 0:
            raise ValueError("StandardRanker must have at least one ranking property")

    def _score(self, trips: list[QueryResult]) -> Iterable[tuple[QueryResult, ScoreInfo]]:
        scores: list[list[list[float]]] = []  # props[trips[flights[score]]]

        for prop in self.properties:
            scores.append([[prop.apply(flight) for flight in trip.trip.flights]
                           for trip in trips])
            scores[-1] = [[prop.normalize(v) for v in row] for row in scores[-1]]
            prop.reset()

        reduced = [[sum(scores) / len(scores) for scores in row] for row in scores]  # props[trips[score]]
        transposed = self._transpose(reduced)  # trips[props[score]]
        for trip, trip_score in zip(trips, transposed):
            final = (sum(s * prop.weight for s, prop in zip(trip_score, self.properties))
                     / sum(prop.weight for prop in self.properties))
            details = {
                "breakdown": [
                    {
                        "prop": type(p).__name__,
                        "val": s,
                    }
                     for s, p in zip(trip_score, self.properties)
                ]
            }
            yield trip, ScoreInfo(score=final, details=details)

    #

    @classmethod
    def _transpose(cls, matrix: list[list[float]]) -> list[list[float]]:
        return [list(r) for r in zip(*matrix)]


#


class AirlineRankProperty(RankProperty):
    preferred_airlines: list[str] = []
    disliked_airlines: list[str] = []

    def _apply(self, flight: Flight, **kwargs) -> float:
        v = 0
        if any(hop.airline in self.preferred_airlines
               for hop in flight.hops):
            v += 1
        if any(hop.airline in self.disliked_airlines
               for hop in flight.hops):
            v -= 1
        return v


class PriceRankProperty(RankProperty):
    inverted: bool = True

    def _apply(self, flight: Flight, **kwargs) -> float:
        return flight.cheapest()


class DurationRankProperty(RankProperty):
    inverted: bool = True

    def _apply(self, flight: Flight, **kwargs) -> float:
        return flight.duration.total_seconds() / 60


class LayoverRankProperty(RankProperty):
    inverted: bool = True

    def _apply(self, flight: Flight, **kwargs) -> float:
        return len(flight.layovers)


class TimeRangeRankProperty(RankProperty):
    class TimeRangeRank(JSONModel):
        start: int
        end: int
        value: float

    time_ranges: list[TimeRangeRank] = []

    def _apply(self, flight: Flight, **kwargs) -> float:
        def _time_score(dt: datetime) -> float:
            for tr in self.time_ranges:
                if tr.start < tr.end and tr.start <= dt.hour < tr.end:
                    return tr.value
                if tr.start > tr.end and (dt.hour <= tr.start or dt.hour < tr.end):
                    return tr.value
            return 0

        return sum((_time_score(flight.departure_time),
                    _time_score(flight.arrival_time))) / 2


class StopRankProperty(RankProperty):
    stop_values: dict[str, int] = {}

    def _apply(self, flight: Flight, **kwargs) -> float:
        return sum(value
                   for stop, value in self.stop_values.items()
                   if stop in flight.stops())


#


class DefaultRanker(StandardRanker):
    properties: set[RankProperty] = {
        PriceRankProperty(weight=3),
        LayoverRankProperty(weight=0.5),
        DurationRankProperty(weight=2),
        TimeRangeRankProperty(time_ranges=[
            TimeRangeRankProperty.TimeRangeRank(start=9, end=22, value=1),
            TimeRangeRankProperty.TimeRangeRank(start=22, end=0, value=0.5),
            TimeRangeRankProperty.TimeRangeRank(start=7, end=9, value=0.5)
        ]),
        AirlineRankProperty(preferred_airlines=["Air France", "Delta", "KLM"],
                            disliked_airlines=["Qatar Airways"])
    }
    extra_properties: list[RankProperty] = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.properties.update(self.extra_properties)
