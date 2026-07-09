from datetime import timedelta

from skyfield.api import load

from config import OBSERVER
from models import ISSPosition


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

    def get_position(self, time = None):
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
    
    