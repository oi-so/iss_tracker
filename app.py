from datetime import datetime, time, timezone

from core.ascom.interface import GuideDirection
from core.ascom.telescope import ASCOMTelescope
from core.astronomy import OrbitCalculator, TLELoader
from core.tracking import Guider, ISSTracker, TrackingConfig, MoveAxisGuider, MoveAxisConfig
from time import sleep


def main():
    tle = TLELoader()
    tle.update(local_path="data/iss.tle", allow_network=False)

    orbit = OrbitCalculator(tle.satellite)
    mount = ASCOMTelescope()
    mount.connect()

    guider = MoveAxisGuider(mount=mount, config=MoveAxisConfig())
    # guider.config.pulse_interval_sec = 0.1

    tracker = ISSTracker(mount=mount, orbit=orbit, guider=guider, config=guider.config)

    start = datetime.now(timezone.utc)
    print(mount.scope.AxisRates(0).Count)

    rates = mount.scope.AxisRates(0)

    for axis in [0,1]:
        rates = mount.scope.AxisRates(axis)
        print(f"Axis {axis}")

        for i in range(1, rates.Count + 1):
            r = rates.Item(i)
            print(i, r.Minimum, r.Maximum)

    mount.disconnect()


if __name__ == "__main__":
    main()