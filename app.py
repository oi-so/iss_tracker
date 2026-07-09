from datetime import datetime, timezone

from core.ascom import MountSimulator
from core.astronomy import OrbitCalculator, TLELoader
from core.tracking import Guider, ISSTracker, TrackingConfig


def main():
    tle = TLELoader()
    tle.update(local_path="data/iss.tle", allow_network=False)

    orbit = OrbitCalculator(tle.satellite)
    mount = MountSimulator()
    mount.connect()

    guider = Guider(mount)
    conf = TrackingConfig()
    conf.pulse_interval_sec = 0.1

    tracker = ISSTracker(mount=mount, orbit=orbit, guider=guider, config=conf)

    start = datetime.now(timezone.utc)
    tracker.acquire(start)
    tracker.start_tracking(start_time=start, duration_sec=30)

    mount.disconnect()


if __name__ == "__main__":
    main()