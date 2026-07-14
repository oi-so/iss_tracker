from datetime import datetime
from zoneinfo import ZoneInfo

import astropy.units as u
from astropy.coordinates import EarthLocation
from astropy.time import Time

from config import OBSERVER


def calculate_lst(when: datetime | None = None) -> float:
    """
    観測地点の地方恒星時(LST)を時間(hour)で返す。

    Args:
        when: UTCまたはタイムゾーン付きdatetime。
              Noneなら現在時刻。

    Returns:
        LST [hour] (0 <= LST < 24)
    """

    OBSERVER_LAT = OBSERVER.latitude.degrees
    OBSERVER_LON = OBSERVER.longitude.degrees

    location = EarthLocation(
        lat=OBSERVER_LAT * u.deg,
        lon=OBSERVER_LON * u.deg,
    )


    t = Time(
        when if when is not None
        else datetime.now(ZoneInfo("Asia/Tokyo"))
    )

    return t.sidereal_time(
        "apparent",
        longitude=location.lon,
    ).hour