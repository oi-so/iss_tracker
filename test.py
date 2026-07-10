from core.astronomy.predictor import Predictor
from core.astronomy.orbit_calculator import OrbitCalculator
from core.astronomy.tle_loader import TLELoader


def main():
    tle = TLELoader()
    tle.update(local_path="data/iss.tle", allow_network=False)

    orbit = OrbitCalculator(tle.satellite)
    predictor = Predictor(orbit)

    positions = predictor.predict(
        duration=5,
        interval=0.5,
    )

    for pos in positions:
        print(
            pos.time.utc_strftime("%H:%M:%S.%f"),
            f"Alt={pos.altitude.degrees:.2f}",
            f"Az={pos.azimuth.degrees:.2f}",
        )

if __name__ == "__main__":
    main()