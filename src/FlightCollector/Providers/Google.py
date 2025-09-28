from __future__ import annotations

from typing import Iterable, Literal, Any, Callable
import fast_flights.core
from fast_flights import FlightData, Passengers as FFPassengers, Result, get_flights
from selectolax.lexbor import LexborHTMLParser, LexborNode
from fast_flights.primp import Response
from datetime import datetime, timedelta, timezone, tzinfo
import itertools
import functools
import airporttime
import re
import asyncio
import pytz
from playwright.async_api import async_playwright
import fast_flights.local_playwright

from Data import Flight, FlightSearch, JourneyType, SeatType, Trip, Hop, Ticket, Passengers, LegSearch
from FlightCollector.FlightCollector import FlightCollector

DATE_FORMAT = "%I:%M %p on %a, %b %d"
DURATION_FORMAT = re.compile(r"(\d+) hr( (\d+) min)?")
LAYOVER_RE = re.compile(r"((\d+) ?hr ?((\d+) ?min)? ?)?([A-Z]{3})")
today = datetime.today()


#


def _parse_date(date: str) -> datetime:
    if date.index(":") == 1:
        date = "0" + date
    parsed = datetime.strptime(date, DATE_FORMAT)
    if parsed.month < today.month or (parsed.month == today.month and parsed.day < today.day):
        parsed = parsed.replace(year=today.year + 1)
    else:
        parsed = parsed.replace(year=today.year)
    return parsed


def _parse_duration(duration: str) -> timedelta:
    try:
        if m := DURATION_FORMAT.match(duration):
            return timedelta(hours=int(m.group(1)), minutes=int(m.group(3)) if m.group(2) else 0)
    except TypeError:
        pass
    return timedelta(0)


def _parse_dates(date_start: str, date_end: str, duration: str,
                 origin: str, destination: str) -> tuple[datetime, datetime]:
    d1, d2 = _parse_date(date_start), _parse_date(date_end)
    # m = DURATION_FORMAT.match(duration)
    # duration = timedelta(hours=int(m.group(1)), minutes=int(m.group(3)) if m.group(2) else 0)
    # delta = d2 - d1
    # offset = round((delta - duration).total_seconds() / 3600)
    def _parse(d: datetime, loc: str) -> datetime:
        if loc == "PKX":
            tz = pytz.timezone("Asia/Shanghai")
            return d.replace(tzinfo=tz)
        try:
            apt = airporttime.AirportTime(iata_code=loc)
            return apt.from_utc(apt.to_utc(d))
        except TypeError:
            return d

    return _parse(d1, origin), _parse(d2, destination)


#


class GoogleSearchCollector(FlightCollector):

    def initialize(self):
        super().initialize()

    def collect(self, search: FlightSearch) -> Iterable[Trip]:
        flight_list: list[list[Flight]] = []
        for leg in search.legs:
            try:
                result: Iterable[Flight] = self._get(date=leg.date.strftime("%Y-%m-%d"),
                                                     origin=leg.origin,
                                                     destination=leg.destination,
                                                     journey=search.journey,
                                                     seat=search.seat,
                                                     passengers=search.passengers)
                flight_list.append([r for r in result if r.info.get("is_best", False)])
            except RuntimeError as e:
                if "No flights found" in str(e):
                    continue
                raise

        combos = itertools.product(*flight_list)
        for combo in combos:
            yield Trip(flights=list(combo))

    @staticmethod
    @functools.cache
    def _get(*, date: str, origin: str, destination: str, journey: JourneyType, seat: SeatType,
             passengers: Passengers) -> Iterable[Flight]:
        fast_flights.core.parse_response = _get_parser(origin=origin, destination=destination, seat=seat)
        return list(get_flights(
            flight_data=[FlightData(date=date,
                                    from_airport=origin,
                                    to_airport=destination)],
            trip=_trip_label(journey),
            seat=_seat_label(seat),
            passengers=FFPassengers(adults=passengers.adults,
                                    children=passengers.children,
                                    infants_in_seat=passengers.infants_in_seat,
                                    infants_on_lap=passengers.infants_on_lap),
            fetch_mode="local"
        ))

    @classmethod
    def is_allowed(cls, search: FlightSearch) -> bool:
        return True


def _trip_label(journey: JourneyType) -> Literal["multi-city", "one-way", "round-trip"]:
    match journey:
        case JourneyType.MultiLeg:
            return "multi-city"
        case JourneyType.OneWay:
            return "one-way"
        case JourneyType.RoundTrip:
            return "round-trip"
    raise NotImplementedError()


def _seat_label(seat: SeatType) -> Literal["economy", "premium-economy", "business", "first"]:
    match seat:
        case SeatType.Economy:
            return "economy"
        case SeatType.EconomyPlus:
            return "premium-economy"
        case SeatType.Business:
            return "business"
        case SeatType.Luxury:
            return "first"
        case _:
            raise NotImplementedError()


def _get_parser(origin: str, destination: str, seat: SeatType) -> Callable[[Response], Iterable[Flight]]:
    def _parse_flights(r: Response) -> Iterable[Flight]:
        class _blank:
            def text(self, *_, **__):
                return ""

            def iter(self):
                return []

        blank = _blank()

        def safe(n: LexborNode | None):
            return n or blank

        parser = LexborHTMLParser(r.text)
        flights = []

        for i, fl in enumerate(parser.css('div[jsname="IWWDBc"], div[jsname="YdtKid"]')):
            is_best_flight = i == 0

            for item in fl.css("ul.Rk10dc li")[:-1]:
                # Flight name
                name = safe(item.css_first("div.sSHqwe.tPgKwe.ogfYpf span")).text(
                    strip=True
                )

                # Get departure & arrival time
                dp_ar_node = item.css("span.mv1WYe div")
                try:
                    departure_time = dp_ar_node[0].text(strip=True)
                    arrival_time = dp_ar_node[1].text(strip=True)
                except IndexError:
                    # sometimes this is not present
                    departure_time = ""
                    arrival_time = ""

                # Get arrival time ahead
                time_ahead = safe(item.css_first("span.bOzv6")).text()

                # Get duration
                lo_duration = safe(item.css_first("li div.Ak5kof div")).text()

                # Get flight stops
                stop_count_str = safe(item.css_first(".BbR8Ec .ogfYpf")).text()

                # Get layovers
                stops = safe(item.css_first(".BbR8Ec .sSHqwe")).text()
                layovers = []
                for stop in stops.split(","):
                    if m := LAYOVER_RE.match(stop):
                        lo_duration = m.group(1)
                        airport = m.group(5)
                        layovers.append({
                            "duration": _parse_duration(lo_duration),
                            "airport": airport,
                        })

                # Get delay
                delay = safe(item.css_first(".GsCCve")).text() or None

                # Get prices
                price_str = safe(item.css_first(".YMlIz.FpEdX")).text() or "0"

                # Stops formatting
                try:
                    stop_count = 0 if stop_count_str == "Nonstop" else int(stop_count_str.split(" ", 1)[0])
                except ValueError:
                    stop_count = "Unknown"

                try:
                    price = float(price_str[1:])
                    currency = price_str[0]
                except ValueError:
                    continue
                dep, arr = _parse_dates(date_start=" ".join(departure_time.split()),
                                        date_end=" ".join(arrival_time.split()),
                                        duration=lo_duration,
                                        origin=origin,
                                        destination=destination)
                airlines = [n.strip() for n in name.split(",")]

                hops = [Hop(origin=origin,
                            destination=destination,
                            departure_time=dep,
                            arrival_time=arr,
                            airline=airlines[0],
                            tickets=[Ticket(price=float(price),
                                            currency=currency,
                                            seat_type=seat,
                                            checked_bags=1,
                                            carryon_bags=1)]
                            )]
                for layover in layovers:
                    stop = layover.get("airport", "?")
                    lo_duration = layover.get("duration", timedelta(0))
                    journey_duration = (hops[-1].arrival_time - hops[-1].departure_time)
                    mid = hops[-1].departure_time + (journey_duration / 2)
                    hops.append(Hop(origin=stop,
                                    destination=hops[-1].destination,
                                    departure_time=mid + (lo_duration / 2),
                                    arrival_time=hops[-1].arrival_time,
                                    airline=airlines[len(hops)] if len(hops) < len(airlines) else "?",
                                    tickets=[Ticket(price=0,
                                                    currency=currency,
                                                    seat_type=seat,
                                                    checked_bags=1,
                                                    carryon_bags=1)]
                                    ))
                    hops[-2].arrival_time = mid - (lo_duration / 2)
                    hops[-2].destination = stop

                yield Flight(hops=hops, info={"is_best": is_best_flight})
    return _parse_flights

    # current_price = safe(parser.css_first("span.gOatQ")).text()
    # if not flights:
    #     raise RuntimeError("No flights found:\n{}".format(r.text_markdown))
    #
    # return Result(current_price=current_price, flights=[Flight(**fl) for fl in flights])


#
# MONKEY PATCHES
def apply_patches():

    async def fetch_with_playwright(url: str) -> str:
        latest_error: Exception | None = None
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            await page.goto(url)
            if page.url.startswith("https://consent.google.com"):
                await page.click('text="Accept all"')

            await asyncio.sleep(3)
            for i in range(5):
                try:
                    body = await page.evaluate(
                        "() => document.querySelector('[role=\"main\"]').innerHTML"
                    )
                except Exception as e:
                    latest_error = e
                    await asyncio.sleep(1)
                    continue
                else:
                    return body
            # await page.wait_for_selector('[role="main"] [role="listitem"]', timeout=30000)t browser.close()
        raise Exception("Could not get the page") from latest_error

    def local_playwright_fetch(params: dict) -> Any:
        url = "https://www.google.com/travel/flights?" + "&".join(f"{k}={v}" for k, v in params.items())
        body = asyncio.run(fetch_with_playwright(url))

        class DummyResponse:
            status_code = 200
            text = body
            text_markdown = body

        return DummyResponse

    fast_flights.local_playwright.fetch_with_playwright = fetch_with_playwright
    fast_flights.local_playwright.local_playwright_fetch = local_playwright_fetch

apply_patches()
