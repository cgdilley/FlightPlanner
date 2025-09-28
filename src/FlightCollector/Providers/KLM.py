from __future__ import annotations

from typing import Iterable
import tomlkit
import httpx
from datetime import date, datetime
import json
import ratelimit
import pytz
import airporttime
from ratelimit import sleep_and_retry

from Data import Flight, JourneyType, FlightSearch, Trip, Passengers, LegSearch, Hop, Ticket
from FlightCollector.FlightCollector import FlightCollector


#


def _parse_datetime(s: str, loc: str) -> datetime:
    d = datetime.fromisoformat(s)
    if loc == "PKX":
        tz = pytz.timezone("Asia/Shanghai")
        return d.replace(tzinfo=tz)
    try:
        apt = airporttime.AirportTime(iata_code=loc)
        return apt.from_utc(apt.to_utc(d))
    except TypeError:
        return d


#


class KLMSearchCollector(FlightCollector):
    API_KEY: str | None = None
    API_URL: str = "https://api.airfranceklm.com/opendata/offers/v3/lowest-fare-offers"
    client: httpx.Client

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client: httpx.Client | None = None
        self.is_initialized = False

    def initialize(self):
        super().initialize()
        if self.API_KEY is None:
            try:
                with open(self._CONFIG_FILE, "r") as f:
                    config = tomlkit.load(f)
                    if "klm" not in config:
                        raise ValueError("KLM API key not found in config file")
                    self.API_KEY = config["klm"]["api_key"]
                    self.API_URL = config["klm"]["api_url"]
            except IOError as e:
                raise ValueError("Config file not found, and KLM API key is not set.") from e
        self.client = httpx.Client(
            headers={"API-Key": self.API_KEY,
                     "Content-Type": "application/hal+json",
                     "AFKL-TRAVEL-Host": "KL"})
        self.is_initialized = True

    def collect(self, search: FlightSearch) -> Iterable[Trip]:
        if not self.is_initialized:
            self.initialize()

        try:
            results = self._request(search)
            if results is not None:
                connections_map: dict[int, Flight] = {
                    connection["id"]: Flight(hops=[Hop(
                        origin=hop["origin"]["code"],
                        destination=hop["destination"]["code"],
                        departure_time=_parse_datetime(hop["departureDateTime"], hop["origin"]["code"]),
                        arrival_time=_parse_datetime(hop["arrivalDateTime"], hop["destination"]["code"]),
                        airline=hop["marketingFlight"]["carrier"]["name"],
                        tickets=[Ticket(price=0, currency=search.currency, seat_type=search.seat,
                                        checked_bags=1, carryon_bags=1)])
                        for hop in connection.get("segments", [])])
                    for leg in results.get("connections", [])
                    for connection in leg
                }

                for recommendation in results.get("recommendations", []):
                    for product in recommendation["flightProducts"]:
                        if any(c["connectionId"] not in connections_map for c in product["connections"]):
                            continue
                        flights = []
                        for connection in product["connections"]:
                            price = connection["price"]["totalPrice"]
                            currency = connection["price"]["currency"]
                            ticket = Ticket(price=price, currency=currency,
                                            checked_bags=1, carryon_bags=1, seat_type=search.seat)
                            flight = connections_map[connection["connectionId"]]
                            flight.hops[0].tickets[0] = ticket
                            flights.append(flight)
                        yield Trip(flights=flights)
            else:
                print("Empty response")

        except Exception as e:
            yield from ()

    @sleep_and_retry
    @ratelimit.limits(calls=1, period=1.5)
    def _request(self, search: FlightSearch) -> dict:
        print(f"Requesting KLM data for the following trips:")
        for leg in search.legs:
            print(f" - ({leg.origin} -> {leg.destination}) on {leg.date:%Y-%m-%d.}")
        res = self.client.post(self.API_URL,
                              json={
                                  "bookingFlow": "LEISURE",
                                  "commercialCabins": ["ECONOMY"],
                                  "passengers": list(self._convert_passengers(search.passengers)),
                                  "currency": search.currency,
                                  "requestedConnections": [
                                      self._convert_leg(leg) for leg in search.legs
                                  ],
                                  "displayPriceContent": "ALL_PAX"
                              })
        if res.is_error:
            raise RuntimeError(f"KLM API error: {res.status_code} {res.reason_phrase}: {res.text}")
        content = res.json()
        return content

    @classmethod
    def is_allowed(cls, search: FlightSearch) -> bool:
        return True

    @classmethod
    def _convert_passengers(cls, passengers: Passengers) -> Iterable[dict]:
        count = 0
        for num, label in ((passengers.adults, "ADT"),):  # TODO: Find out other passenger labels
            for _ in range(num):
                count += 1
                yield {
                    "id": count,
                    "type": label
                }

    @classmethod
    def _convert_leg(cls, leg: LegSearch) -> dict:
        d = cls._date_format(leg.date)
        return {
            "departureDate": d,
            "dateInterval": f"{d}/{d}",
            "origin": {
                "type": "AIRPORT",
                "code": leg.origin
            },
            "destination": {
                "type": "AIRPORT",
                "code": leg.destination
            }
        }

    @classmethod
    def _date_format(cls, d: date) -> str:
        return d.strftime("%Y-%m-%d")
