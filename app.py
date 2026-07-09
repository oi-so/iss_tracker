from orbit import OrbitCalculator
from telescope_simulator import MountSimulator
from tracker import Tracker
from tle import TLELoader
from guider import Guider
from datetime import datetime
from zoneinfo import ZoneInfo


def main():

    tle = TLELoader()
    tle.update()

    orbit = OrbitCalculator(tle.satellite)
    mount = MountSimulator()

    guider = Guider(mount)

    tracker = Tracker(
        orbit,
        mount,
        guider,
    )

    start = orbit.ts.from_datetime(
        datetime(
            2026,
            7,
            9,
            19,
            51,
            0,
            tzinfo=ZoneInfo("Asia/Tokyo"),
        )
    )

    tracker.track(
        duration=300,
        interval=0.05,
        base_time=start,
    )


if __name__ == "__main__":
    main()