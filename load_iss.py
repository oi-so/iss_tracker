from core.astronomy.tle_loader import TLELoader


def main():
    tle = TLELoader()
    tle.update(local_path="data/iss.tle", allow_network=False)


if __name__ == "__main__":
    main()