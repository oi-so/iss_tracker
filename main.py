from orbit import OrbitCalculator
from telescope import Telescope
from tracker import Tracker
from tle import TLELoader
from guider import Guider

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import time


def main():

    # -------------------------
    # TLE
    # -------------------------

    tle = TLELoader()
    tle.update()

    orbit = OrbitCalculator(
        tle.satellite
    )


    # -------------------------
    # Telescope
    # -------------------------

    telescope = Telescope()

    telescope.connect()


    try:

        # -------------------------
        # 現在位置確認
        # -------------------------

        ra, dec = telescope.get_position()

        print(
            f"Current position "
            f"RA={ra:.4f}deg "
            f"DEC={dec:.4f}deg"
        )

        # return


        # -------------------------
        # 追尾開始時刻
        # -------------------------

        track_start = datetime(
            2026,
            7,
            9,
            19,
            51,
            00,
            tzinfo=ZoneInfo(
                "Asia/Tokyo"
            )
        )


        now = datetime.now(
            ZoneInfo("Asia/Tokyo")
        )


        wait = (
            track_start - now
        ).total_seconds()


        if wait > 0:

            print(
                f"Waiting {wait:.1f}s"
            )

            time.sleep(wait)



        # -------------------------
        # ISS導入
        # -------------------------

        skyfield_time = orbit.ts.from_datetime(
            track_start
        )


        # GoToにかかる時間を考慮
        goto_delay = 20


        target = orbit.get_position_after(
            skyfield_time,
            goto_delay
        )


        print(
            "ISS target:"
            f"RA={target.ra.hours:.4f}h "
            f"DEC={target.dec.degrees:.4f}deg"
        )


        telescope.goto(
            target.ra,
            target.dec
        )


        print(
            "Slewing..."
        )


        telescope.wait_slew()


        print(
            "Slew completed"
        )



        # -------------------------
        # 追尾開始
        # -------------------------

        guider = Guider(
            telescope
        )


        tracker = Tracker(
            orbit,
            telescope,
            guider,
        )


        tracker.track(
            duration=300,
            interval=0.05,
            base_time=skyfield_time,
        )


    finally:

        telescope.disconnect()



if __name__ == "__main__":
    main()