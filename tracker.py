import time


class Tracker:

    def __init__(
        self,
        orbit,
        mount,
        guider,
    ):
        self.orbit = orbit
        self.mount = mount
        self.guider = guider


    def track(
        self,
        duration,
        interval,
        base_time,
    ):

        start_real = time.perf_counter()

        next_update = start_real


        while True:

            elapsed = time.perf_counter() - start_real

            if elapsed > duration:
                break


            # 現在のISS位置
            position = self.orbit.get_position_after(
                base_time,
                elapsed,
            )


            # 少し未来のISS位置
            future_position = self.orbit.get_position_after(
                base_time,
                elapsed + interval,
            )


            iss_ra = position.ra.hours * 15
            iss_dec = position.dec.degrees


            future_ra = future_position.ra.hours * 15
            future_dec = future_position.dec.degrees


            # ISS角速度
            ra_velocity = (
                future_ra - iss_ra
            ) / interval


            dec_velocity = (
                future_dec - iss_dec
            ) / interval



            mount_ra, mount_dec = (
                self.mount.get_position()
            )


            ra_error = iss_ra - mount_ra
            dec_error = iss_dec - mount_dec


            self.guider.guide(
                ra_velocity,
                dec_velocity,
                ra_error,
                dec_error,
            )


            self.mount.update(interval)



            print(
                f"ISS   : {iss_ra:.2f} {iss_dec:.2f}"
            )
            print(
                f"Mount : {mount_ra:.2f} {mount_dec:.2f}"
            )
            print(
                f"Error : {ra_error:.2f} {dec_error:.2f}"
            )
            print(
                f"Speed : {ra_velocity:.3f} "
                f"{dec_velocity:.3f}"
            )
            print()


            next_update += interval

            sleep = next_update - time.perf_counter()

            if sleep > 0:
                time.sleep(sleep)