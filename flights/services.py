
# flights/services.py
from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
from django.conf import settings
from django.core.cache import cache


def iso8601_duration_to_hm(d: str) -> str:
    if not d:
        return ""
    m = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$", d)
    if not m:
        return d
    h = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return f"{h}h {mins:02d}m"


def hhmm_from_iso(dt: str) -> str:
    if not dt:
        return ""
    return dt[11:16] if len(dt) >= 16 else dt


def day_offset(dep_iso: str, arr_iso: str) -> int:
    if not dep_iso or not arr_iso or len(dep_iso) < 10 or len(arr_iso) < 10:
        return 0
    dep_d = date.fromisoformat(dep_iso[:10])
    arr_d = date.fromisoformat(arr_iso[:10])
    return (arr_d - dep_d).days


class AmadeusService:
    TOKEN_URL = {
        "test": "https://test.api.amadeus.com/v1/security/oauth2/token",
        "production": "https://api.amadeus.com/v1/security/oauth2/token",
    }
    SEARCH_URL = {
        "test": "https://test.api.amadeus.com/v2/shopping/flight-offers",
        "production": "https://api.amadeus.com/v2/shopping/flight-offers",
    }

    def __init__(self) -> None:
        self.client_id = (settings.AMADEUS_CLIENT_ID or "").strip()
        self.client_secret = (settings.AMADEUS_CLIENT_SECRET or "").strip()
        env = (settings.AMADEUS_HOSTNAME or "test").strip()
        self.env = env if env in self.TOKEN_URL else "test"

    def credentials_present(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> str:
        if not self.credentials_present():
            raise ValueError("AMADEUS credentials missing")

        cache_key = f"amadeus_token:{self.env}"
        token = cache.get(cache_key)
        if token:
            return token

        r = requests.post(
            self.TOKEN_URL[self.env],
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=20,
        )
        r.raise_for_status()
        payload = r.json()

        token = payload["access_token"]
        ttl = int(payload.get("expires_in", 1800))
        ttl = max(60, ttl - 60)
        cache.set(cache_key, token, ttl)
        return token

    def search_offers(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: Optional[str],
        adults: int,
        max_results: int = 10,
        currency: str = "USD",
    ) -> Dict[str, Any]:
        token = self._get_token()

        params: Dict[str, Any] = {
            "originLocationCode": origin,
            "destinationLocationCode": destination,
            "departureDate": departure_date,
            "adults": adults,
            "max": max_results,
            "currencyCode": currency,
        }
        if return_date:
            params["returnDate"] = return_date

        r = requests.get(
            self.SEARCH_URL[self.env],
            headers={"Authorization": f"Bearer {token}"},
            params=params,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()

    def normalize_offers(self, amadeus_payload: Dict[str, Any]) -> List[Dict[str, Any]]:
        dictionaries = amadeus_payload.get("dictionaries") or {}
        carriers = dictionaries.get("carriers") or {}
        aircraft = dictionaries.get("aircraft") or {}

        offers_out: List[Dict[str, Any]] = []
        seen_keys: Set[Tuple] = set()

        for offer in amadeus_payload.get("data", []) or []:
            itineraries = offer.get("itineraries") or []
            if not itineraries:
                continue

            out_itin = self._normalize_itinerary(itineraries[0], carriers, aircraft)
            in_itin = self._normalize_itinerary(itineraries[1], carriers, aircraft) if len(itineraries) > 1 else None

            # Codeshare dedupe: operating carrier + dep_at + origin + destination
            first_seg = out_itin["segments"][0] if out_itin["segments"] else {}
            op_key = (
                first_seg.get("operating_carrier", ""),
                out_itin["dep_at"],
                out_itin["origin"],
                out_itin["destination"],
            )
            if op_key in seen_keys:
                continue
            seen_keys.add(op_key)

            offers_out.append(
                {
                    "id": offer.get("id", ""),
                    "outbound": out_itin,
                    "inbound": in_itin,
                }
            )

        return offers_out

    def _normalize_itinerary(self, itin: Dict[str, Any], carriers: Dict[str, str], aircraft: Dict[str, str]) -> Dict[str, Any]:
        segs = itin.get("segments") or []
        if not segs:
            return {
                "origin": "",
                "destination": "",
                "dep": "",
                "arr": "",
                "dep_at": "",
                "arr_at": "",
                "arr_day_offset": 0,
                "duration": iso8601_duration_to_hm(itin.get("duration", "")),
                "stops": 0,
                "segments": [],
            }

        first = segs[0]
        last = segs[-1]

        origin = first["departure"]["iataCode"]
        destination = last["arrival"]["iataCode"]

        dep_iso = first["departure"]["at"]
        arr_iso = last["arrival"]["at"]

        segments_out: List[Dict[str, Any]] = []
        for s in segs:
            ccode = s.get("carrierCode", "")
            op_code = (s.get("operating") or {}).get("carrierCode", "") or ccode
            op_name = carriers.get(op_code, op_code) if op_code else ""
            cname = carriers.get(ccode, ccode) if ccode else ""
            fnum = s.get("number", "")
            flight_number = f"{op_code}{fnum}" if op_code and fnum else ""

            acode = (s.get("aircraft") or {}).get("code", "")
            aname = aircraft.get(acode, acode) if acode else ""

            dep_s_iso = s["departure"]["at"]
            arr_s_iso = s["arrival"]["at"]

            segments_out.append(
                {
                    "carrier_code": ccode,
                    "carrier_name": cname,
                    "operating_carrier": op_code,
                    "operating_carrier_name": op_name,
                    "flight_number": flight_number,
                    "aircraft_code": aname,
                    "departure_airport": s["departure"]["iataCode"],
                    "arrival_airport": s["arrival"]["iataCode"],
                    "departure_time": hhmm_from_iso(dep_s_iso),
                    "arrival_time": hhmm_from_iso(arr_s_iso),
                    "departure_at": dep_s_iso,
                    "arrival_at": arr_s_iso,
                    "arr_day_offset": day_offset(dep_s_iso, arr_s_iso),
                    "duration": iso8601_duration_to_hm(s.get("duration", "")),
                }
            )

        return {
            "origin": origin,
            "destination": destination,
            "dep": hhmm_from_iso(dep_iso),
            "arr": hhmm_from_iso(arr_iso),
            "dep_at": dep_iso,
            "arr_at": arr_iso,
            "arr_day_offset": day_offset(dep_iso, arr_iso),
            "duration": iso8601_duration_to_hm(itin.get("duration", "")),
            "stops": max(0, len(segs) - 1),
            "segments": segments_out,
        }
