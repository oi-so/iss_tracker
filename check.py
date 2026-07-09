from tle import Telescope
import time


def main():

    telescope = Telescope()

    telescope.connect()

    try:
        while True:

            ra = telescope.scope.RightAscension
            dec = telescope.scope.Declination

            print(
                f"RA={ra:.6f}h "
                f"DEC={dec:.6f}deg"
            )

            time.sleep(1)

    finally:
        telescope.disconnect()


if __name__ == "__main__":
    main()