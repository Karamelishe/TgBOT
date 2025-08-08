from __future__ import annotations

from datetime import datetime
from typing import Tuple, List
import pytz


def local_to_utc_iso(local_dt_str: str, tz_name: str) -> str:
    # local_dt_str: "YYYY-MM-DD HH:MM"
    tz = pytz.timezone(tz_name)
    naive = datetime.strptime(local_dt_str, "%Y-%m-%d %H:%M")
    local = tz.localize(naive)
    return local.astimezone(pytz.utc).isoformat()


def utc_iso_to_local_str(utc_iso: str, tz_name: str) -> Tuple[str, str]:
    # returns (date_str YYYY-MM-DD, time_str HH:MM)
    tz = pytz.timezone(tz_name)
    dt_utc = datetime.fromisoformat(utc_iso)
    local = dt_utc.astimezone(tz)
    return local.strftime("%Y-%m-%d"), local.strftime("%H:%M")


def unique_sorted_dates_local(utc_isos: List[str], tz_name: str) -> List[str]:
    seen = set()
    dates: List[str] = []
    for iso in utc_isos:
        d, _ = utc_iso_to_local_str(iso, tz_name)
        if d not in seen:
            seen.add(d)
            dates.append(d)
    dates.sort()
    return dates