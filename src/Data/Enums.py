from __future__ import annotations

from enum import Enum
from typing import Iterable, Collection


class JourneyType(Enum):
    OneWay = 1
    RoundTrip = 2
    MultiLeg = 3

    @classmethod
    def infer(cls, *jumps: tuple[str, str]) -> JourneyType:
        if len(jumps) == 1:
            return JourneyType.OneWay
        elif len(jumps) == 2 and jumps[0][0] == jumps[1][1] \
                and jumps[0][1] == jumps[1][0]:
            return JourneyType.RoundTrip
        else:
            return JourneyType.MultiLeg


class SeatType(Enum):
    Economy = 0
    EconomyPlus = 5
    Premium = 10
    Business = 15
    Luxury = 20
