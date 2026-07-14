from datetime import time, timedelta

from skyfield.api import load

from config import OBSERVER
from models import ISSPosition
from skyfield.api import wgs84


class OrbitCalculator:
    def __init__(self, satellite):
        self.satellite = satellite
        self.ts = load.timescale()

    def _calc(self, t):
        difference = self.satellite - OBSERVER
        topocentric = difference.at(t)

        ra, dec, distance = topocentric.radec()
        alt, az, _ = topocentric.altaz()

        return ISSPosition(
            time=t,
            ra=ra,
            dec=dec,
            distance=distance,
            altitude=alt,
            azimuth=az,
        )

    def get_position(self, time=None):
        if time is None:
            time = self.ts.now()
        return self.get_position_at(time)

    def get_position_after(self, base_time, seconds):
        future = self.ts.from_datetime(
            base_time.utc_datetime() + timedelta(seconds=seconds)
        )
        return self._calc(future)

    def get_position_at(self, t):
        return self._calc(t)



    def local_sidereal_time(self, time=None):
        """
        観測地点の地方恒星時 [hours]
        """

        if time is None:
            t = self.ts.now()

        elif hasattr(time, "gmst"):
            t = time

        else:
            t = self.ts.from_datetime(time)

        lst = t.gmst + OBSERVER.longitude.degrees / 15.0

        return lst % 24
    

    @staticmethod
    def _normalize_hours(hours: float) -> float:
        """-12～+12hへ正規化"""
        while hours > 12:
            hours -= 24
        while hours < -12:
            hours += 24
        return hours



    def hour_angle(self, time):
        pos = self.get_position_at(
            self.ts.from_datetime(time)
        )

        ha = self.local_sidereal_time(time) - pos.ra.hours

        return self._normalize_hours(ha)