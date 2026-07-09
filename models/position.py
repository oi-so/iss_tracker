from dataclasses import dataclass

from skyfield.timelib import Time
from skyfield.units import Angle, Distance


@dataclass
class ISSPosition:
    time: Time
    ra: Angle
    dec: Angle
    distance: Distance
    altitude: Angle
    azimuth: Angle
