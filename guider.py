class Guider:

    def __init__(
        self,
        mount,
    ):
        self.mount = mount

        self.kp = 0.05


    def guide(
        self,
        ra_velocity,
        dec_velocity,
        ra_error,
        dec_error,
    ):


        # 予測追尾速度
        ra_rate = ra_velocity
        dec_rate = dec_velocity


        # 誤差補正
        ra_rate += ra_error * self.kp
        dec_rate += dec_error * self.kp


        self.mount.pulse_guide(
            ra_rate,
            dec_rate,
            0.05,
        )