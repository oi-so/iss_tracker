import time
import win32com.client


class Telescope:

    def __init__(self, simulate=False):
        self.scope = None
        self.simulate = simulate

        # シミュレーション用現在位置
        self.sim_ra = 0.0
        self.sim_dec = 0.0


    def connect(self):

        if self.simulate:
            print("Simulation telescope connected")
            return

        chooser = win32com.client.Dispatch(
            "ASCOM.Utilities.Chooser"
        )

        chooser.DeviceType = "Telescope"

        progid = chooser.Choose(None)

        if progid is None:
            raise RuntimeError(
                "Telescope driver was not selected"
            )

        print("Driver:", progid)

        self.scope = win32com.client.Dispatch(
            progid
        )

        self.scope.Connected = True

        print("Connected!")


    def disconnect(self):

        if self.simulate:
            print("Simulation telescope disconnected")
            return

        if self.scope is not None:

            self.scope.Connected = False
            self.scope = None

            print("Disconnected")


    def is_connected(self):

        if self.simulate:
            return True

        return self.scope is not None and self.scope.Connected


    def get_position(self):

        """
        現在向いている赤経赤緯を取得

        Returns:
            ra : degree
            dec: degree
        """

        if self.simulate:

            return (
                self.sim_ra,
                self.sim_dec
            )


        if not self.is_connected():
            raise RuntimeError(
                "Telescope is not connected"
            )


        # ASCOMはRAがhour単位
        ra = self.scope.RightAscension * 15.0
        dec = self.scope.Declination

        return (
            ra,
            dec
        )


    def goto(self, ra, dec):

        """
        GoTo実行

        ra:
            Skyfield Angle

        dec:
            Skyfield Angle
        """

        if self.simulate:

            self.sim_ra = ra.degrees
            self.sim_dec = dec.degrees

            print(
                f"GOTO "
                f"RA={self.sim_ra:.4f}deg "
                f"DEC={self.sim_dec:.4f}deg"
            )

            return


        if not self.is_connected():
            raise RuntimeError(
                "Telescope is not connected"
            )


        self.scope.SlewToCoordinatesAsync(
            ra.hours,
            dec.degrees
        )


    def wait_slew(
        self,
        interval=0.1,
        timeout=300
    ):

        """
        GoTo完了待機
        """

        if self.simulate:

            return


        start = time.time()


        while self.scope.Slewing:

            if time.time() - start > timeout:
                raise TimeoutError(
                    "Slew timeout"
                )

            time.sleep(interval)



    def pulse_guide(
        self,
        direction,
        duration_ms
    ):

        """
        PulseGuide

        direction:
            ASCOM方向

        duration_ms:
            ミリ秒
        """

        if self.simulate:

            print(
                f"PulseGuide "
                f"{direction} "
                f"{duration_ms}ms"
            )

            return


        if not self.is_connected():
            raise RuntimeError(
                "Telescope is not connected"
            )


        self.scope.PulseGuide(
            direction,
            duration_ms
        )