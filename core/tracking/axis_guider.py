from core.tracking.guider import Guider


class MoveAxisConfig:
    kp = 0.15

    # ASCOM AxisRatesで取得した範囲
    axis_rates = [
        (0.002089, 0.004178),
        (0.004179, 0.033425),
        (0.033426, 0.066849),
        (0.066850, 0.208904),
    ]

    dead_band_deg = 0.0005


class MoveAxisGuider(Guider):

    def __init__(self, mount, config=None):
        super().__init__(mount, config or MoveAxisConfig())


    def guide(
        self,
        ra_velocity_deg_per_sec,
        dec_velocity_deg_per_sec,
        ra_error_deg,
        dec_error_deg,
    ):
        """
        ISS角速度を基本速度として、
        位置誤差による補正を少量加える
        """

        ra_rate = (
            ra_velocity_deg_per_sec
            + self.config.kp * ra_error_deg
        )

        dec_rate = (
            dec_velocity_deg_per_sec
            + self.config.kp * dec_error_deg
        )

        self._execute_move_axis(
            ra_rate,
            dec_rate,
        )


    def _execute_move_axis(
        self,
        ra_rate,
        dec_rate,
    ):

        ra_rate = self.limit_rate(ra_rate)
        dec_rate = self.limit_rate(dec_rate)

        if abs(ra_rate) < self.config.dead_band_deg:
            ra_rate = 0

        if abs(dec_rate) < self.config.dead_band_deg:
            dec_rate = 0

        # RA方向は符号反転（現在の赤道儀設定に合わせる）
        self.mount.move_axis(0, -ra_rate)

        # DEC方向
        self.mount.move_axis(1, dec_rate)


    def limit_rate(self, rate):
        """
        E-ZEUS IIのAxisRates範囲内に制限
        範囲内なら値をそのまま使用する
        """

        if rate == 0:
            return 0

        sign = 1 if rate > 0 else -1
        rate_abs = abs(rate)

        minimum = self.config.axis_rates[0][0]
        maximum = self.config.axis_rates[-1][1]

        # 最低速度未満
        if rate_abs < minimum:
            return 0

        # 最大速度以上
        if rate_abs > maximum:
            return sign * maximum

        return sign * rate_abs


    def stop(self):
        self.mount.move_axis(0, 0)
        self.mount.move_axis(1, 0)