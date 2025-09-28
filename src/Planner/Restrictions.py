from __future__ import annotations

from SprelfJSON import JSONModel
from abc import ABC, abstractmethod

from FlightCollector import FlightCollector
from Planner.Query import PlannedQuery


#


class SearchRestriction(JSONModel, ABC):

    @abstractmethod
    def restrict(self, search: PlannedQuery):
        ...

    @classmethod
    def apply(cls, query: PlannedQuery, *restrictions: SearchRestriction):
        for restriction in restrictions:
            if not (query := restriction.restrict(query)):
                return None
        return query


#


class CollectorLegRestriction(SearchRestriction):
    collectors: set[type[FlightCollector]]
    origins: set[str]
    destinations: set[str]

    def restrict(self, search: PlannedQuery) -> PlannedQuery | None:
        if search.collector in self.collectors:
            search.search.legs = [leg for leg in search.search.legs
                                  if not (leg.origin in self.origins and leg.destination in self.destinations)]
            if len(search.search.legs) == 0:
                return None
        return search


class CollectorJourneyRestriction(SearchRestriction):
    collectors: set[type[FlightCollector]]
    origins: set[str]
    destinations: set[str]

    def restrict(self, search: PlannedQuery) -> PlannedQuery | None:
        if search.collector in self.collectors and \
                search.search.legs[0].origin in self.origins and \
                search.search.legs[-1].destination in self.destinations:
            return None
        return search
