from __future__ import annotations

from SprelfJSON import JSONModel
from abc import ABC, abstractmethod
from typing import Iterable

from Data import FlightOptions, Flight, FlightSearch, SeatType
from FlightCollector import FlightCollector
from Planner.Query import PlannedQuery, QueryResult, ScoredQueryResult
from Planner.Restrictions import SearchRestriction
from Planner.Ranking import Ranker, DefaultRanker


#

class PlanResult(JSONModel):
    name: str
    results: list[ScoredQueryResult]


class SearchPlan(JSONModel):
    options: list[FlightOptions]
    collectors: list[type[FlightCollector]]
    restrictions: list[SearchRestriction] = []
    ranker: Ranker = DefaultRanker()

    def queries(self, options: FlightOptions) -> Iterable[PlannedQuery]:
        for collector in self.collectors:
            for search in options:
                if collector.is_allowed(search):
                    if pq := SearchRestriction.apply(PlannedQuery(collector=collector, search=search),
                                                     *self.restrictions):
                        yield pq

    def search(self) -> Iterable[PlanResult]:
        for fo in self.options:
            yield PlanResult(name=fo.name, results=list(self._rank(self._search_for_options(fo))))

    def _search_for_options(self, options: FlightOptions) -> Iterable[QueryResult]:
        for query in self.queries(options):
            with query.collector() as collector:
                trips = collector.collect(query.search)
                yield from (QueryResult(collector=query.collector, trip=t) for t in trips
                            if all(filt.filter(flight) for filt in options.filters for flight in t.flights))


    def _rank(self, queries: Iterable[QueryResult]) -> Iterable[ScoredQueryResult]:
        yield from self.ranker.rank(queries)
