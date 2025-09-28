from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, Self
from types import TracebackType
import pathlib
import os

from Data import Flight, FlightSearch, Trip


_HOME = str(pathlib.Path.home())

#


class FlightCollector(ABC):
    _CONFIG_FILE: str = os.path.join(_HOME, ".flights/config.toml")

    def initialize(self):
        ...

    def close(self):
        ...

    def __enter__(self) -> Self:
        self.initialize()
        return self

    def __exit__(self, exc_type: type[BaseException] | None,
                 exc_val: BaseException | None,
                 exc_tb: TracebackType | None) -> bool:
        self.close()
        return False

    @abstractmethod
    def collect(self, search: FlightSearch) -> Iterable[Trip]:
        ...

    @classmethod
    @abstractmethod
    def is_allowed(cls, search: FlightSearch) -> bool:
        ...


