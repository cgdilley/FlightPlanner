from __future__ import annotations

from SprelfJSON import JSONModel

from Data import Flight, FlightSearch, Trip
from FlightCollector.FlightCollector import FlightCollector


#


class PlannedQuery(JSONModel):
    __eval_context__ = {**JSONModel.__eval_context__, FlightCollector.__name__: FlightCollector}
    collector: type[FlightCollector]
    search: FlightSearch


class QueryResult(JSONModel):
    collector: type[FlightCollector]
    trip: Trip


class ScoreInfo(JSONModel):
    score: float
    details: dict = {}

    def __lt__(self, other: ScoreInfo) -> bool:
        return self.score < other.score


class ScoredQueryResult(JSONModel):
    __D_FORMAT = "%a %d %b, %Y (%H:%M)"
    query: QueryResult
    score: ScoreInfo
    rank: int

    def __init__(self, **kwargs):
        if isinstance(kwargs["score"], float):
            kwargs["score"] = ScoreInfo(score=kwargs["score"])
        super().__init__(**kwargs)

    @property
    def provider(self) -> type[FlightCollector]:
        return self.query.collector

    def __str__(self) -> str:
        r = self.query
        s = f"Score = {self.score.score:.4f}\n" \
            f"[{r.collector.__name__}]\n" \
            f" {r.trip.cheapest():.0f} {r.trip.currency}\n"
        for f in r.trip.flights:
            s += f"  * {f.departure_time.strftime(self.__D_FORMAT)} - {f.arrival_time.strftime(self.__D_FORMAT)}\n" \
                 f"    {int(f.duration.total_seconds() // 3600)}h{int((f.duration.total_seconds() % 3600) // 60):02d}\n" \
                 f"    {f.cheapest():.0f} {f.currency}, {'|'.join(s.name for s in f.seats())}, {'/'.join(h.airline for h in f.hops)}\n" \
                 f"    {' -> '.join(f.stops())}\n\n"
        return s
