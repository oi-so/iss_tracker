from dataclasses import dataclass
from datetime import datetime
from dataclasses import dataclass
from datetime import datetime, timedelta



@dataclass
class WaitingPosition:
    time: datetime
    ra_hours: float
    dec_degrees: float


@dataclass
class PassAnalysis:
    requires_flip: bool
    flip_time: datetime | None

    recommended_start: datetime
    waiting_position: WaitingPosition | None



class PassAnalyzer:
    def __init__(self, orbit):
        """
        Parameters
        ----------
        orbit : OrbitCalculator
        calculate_lst : callable(datetime) -> float
            指定時刻のLST(h)を返す関数
        """
        self.orbit = orbit



    def analyze(
        self,
        rise_time: datetime,
        track_start: datetime,
        set_time: datetime,
        interval_sec: float = 0.5,
        wait_margin_sec: float = 5.0,
    ) -> PassAnalysis:
        previous = self.orbit.hour_angle(track_start)

        flip_time = None

        t = track_start

        while t <= set_time:

            ha = self.orbit.hour_angle(t)

            if previous > 0 >= ha or previous < 0 <= ha:
                flip_time = t
                break

            previous = ha
            t += timedelta(seconds=interval_sec)

        requires_flip = flip_time is not None


        waiting = None
        recommended_start = track_start

        if requires_flip:

            recommended_start = flip_time + timedelta(
                seconds=wait_margin_sec
            )

            pos = self.orbit.get_position_at(
                self.orbit.ts.from_datetime(recommended_start)
            )

            waiting = WaitingPosition(
                time=recommended_start,
                ra_hours=pos.ra.hours,
                dec_degrees=pos.dec.degrees,
            )


        return PassAnalysis(
            requires_flip=requires_flip,
            flip_time=flip_time,
            recommended_start=recommended_start,
            waiting_position=waiting,
        )