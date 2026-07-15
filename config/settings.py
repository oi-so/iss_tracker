from pathlib import Path

from skyfield.api import wgs84

# 立川高校（おおよその位置）
OBSERVER = wgs84.latlon(
    latitude_degrees=35.6924639,
    longitude_degrees=139.4128300,
    elevation_m=95,
)


TLE_URL = "https://celestrak.org/NORAD/elements/gp.php?GROUP=stations&FORMAT=tle"

# オフライン環境向け: 既定のローカルTLEファイル
DEFAULT_LOCAL_TLE_PATH = Path("data") / "iss.tle"
