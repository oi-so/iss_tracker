import requests

from skyfield.api import EarthSatellite

from config import TLE_URL


class TLELoader:

    def __init__(self):
        self.satellite = None

    def update(self):

        text = requests.get(TLE_URL, timeout=10).text

        lines = text.splitlines()

        for i, line in enumerate(lines):

            if "ISS" in line:

                name = lines[i]
                tle1 = lines[i + 1]
                tle2 = lines[i + 2]

                self.satellite = EarthSatellite(
                    tle1,
                    tle2,
                    name,
                )

                return

        raise RuntimeError("ISS TLEが見つかりません")