from core.ascom.telescope import Telescope
import time


def main():
    telescope = Telescope()
    telescope.connect()

    try:
        while True:
            pos = telescope.get_position()

            print(
                f"RA={pos.ra_hours:.6f}h "
                f"DEC={pos.dec_degrees:.6f}deg"
            )
            time.sleep(1)

    finally:
        telescope.disconnect()


if __name__ == "__main__":
    main()