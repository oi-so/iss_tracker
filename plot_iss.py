import matplotlib.pyplot as plt

from core.astronomy import TLELoader, OrbitCalculator, Predictor
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

import argparse


def parse_args():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--simulate-time",
        type=str,
        default=None,
        help="シミュレーション開始時刻 (YYYY/MM/DD HH:MM:SS, JST)",
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="予測時間(秒)",
    )

    parser.add_argument(
        "--interval",
        type=int,
        default=5,
        help="計算間隔(秒)",
    )

    return parser.parse_args()


def parse_simulate_time(value, ts):
    if value is None:
        return ts.now()

    dt = datetime.strptime(
        value,
        "%Y/%m/%d %H:%M:%S"
    )

    dt = dt.replace(tzinfo=JST)

    return ts.from_datetime(dt)

def find_pass_events(positions):
    """
    ISSの全パスの出現・最大高度・消滅を探す
    高度0度を境界とする
    """

    passes = []

    current = None

    altitudes = [
        p.altitude.degrees
        for p in positions
    ]


    for i, p in enumerate(positions):

        alt = altitudes[i]


        # 出現
        if i == 0:
            if alt > 0:
                current = {
                    "rise": p,
                    "max": p,
                }

        elif altitudes[i-1] <= 0 and alt > 0:
            current = {
                "rise": p,
                "max": p,
            }


        # 可視中
        if current is not None:

            if p.altitude.degrees > current["max"].altitude.degrees:
                current["max"] = p


        # 消滅
        if (
            current is not None
            and i > 0
            and altitudes[i-1] > 0
            and alt <= 0
        ):
            current["set"] = p

            passes.append(current)
            current = None


    # 最後まで可視だった場合
    if current is not None:
        passes.append(current)


    return passes


def print_position(p, index):
    """
    ISS位置表示
    """

    jst = p.time.utc_datetime().astimezone(JST)

    print(
        f"[{index:03d}] "
        f"{jst:%Y/%m/%d %H:%M:%S} JST | "
        f"RA={p.ra.hours:.4f}h "
        f"DEC={p.dec.degrees:.3f}° | "
        f"ALT={p.altitude.degrees:.2f}° "
        f"AZ={p.azimuth.degrees:.2f}°"
    )


def main():

    args = parse_args()

    print("=== ISS Orbit Plot ===")

    loader = TLELoader()
    loader.update(allow_network=True, force_reload=True)

    print(
        f"TLE loaded: {loader.satellite.name}"
    )


    orbit = OrbitCalculator(loader.satellite)

    predictor = Predictor(orbit)


    base_time = parse_simulate_time(
        args.simulate_time,
        orbit.ts
    )
    print(base_time.utc_datetime())


    print(
        "Simulation start:",
        base_time.utc_datetime()
        .astimezone(JST)
        .strftime("%Y/%m/%d %H:%M:%S JST")
    )


    end_time = base_time + args.duration / 86400

    print(
        "Simulation end:",
        end_time.utc_datetime()
        .astimezone(JST)
        .strftime("%Y/%m/%d %H:%M:%S JST")
    )


    positions = predictor.predict(
        duration=args.duration,
        interval=args.interval,
        base_time=base_time
    )

    passes = find_pass_events(positions)


    print()
    print("--- Sample positions ---")


    # 最初・1分後・最後などを見る
    indexes = {
        0,
        len(positions)//2,
        len(positions)-1
    }


    for i in sorted(indexes):
        print_position(
            positions[i],
            i
        )


    az = []
    alt = []
    times = []

    for p in positions:
        az.append(p.azimuth.degrees)
        alt.append(p.altitude.degrees)

        times.append(
            p.time.utc_datetime()
            .astimezone(JST)
        )

    plt.plot(
        az,
        alt,
        marker="o"
    )

    for i, iss_pass in enumerate(passes):
        print(
            f"Pass {i+1}"
        )


        for name in ["rise", "max", "set"]:

            p = iss_pass[name]

            event_time = (
                p.time.utc_datetime()
                .astimezone(JST)
            )


            az_event = p.azimuth.degrees
            alt_event = p.altitude.degrees


            label = (
                f"Pass {i+1} {name}\n"
                f"{event_time:%H:%M:%S}"
            )


            plt.scatter(
                az_event,
                alt_event
            )


            plt.annotate(
                label,
                (az_event, alt_event),
                xytext=(10,10),
                textcoords="offset points",
                fontsize=8
            )


    # 時刻ラベルを表示する点
    indexes = [
        0,
        len(positions)//2,
        len(positions)-1
    ]


    for i in indexes:
        plt.annotate(
            times[i].strftime("%H:%M:%S"),
            (
                az[i],
                alt[i]
            ),
            textcoords="offset points",
            xytext=(5, 5),
            fontsize=9
        )

    print("\n=== ISS Passes ===")

    for i, p in enumerate(passes):

        print(
            f"Pass {i+1}"
        )

        for key in ["rise", "max", "set"]:

            t = (
                p[key].time
                .utc_datetime()
                .astimezone(JST)
            )

            print(
                f"  {key}: "
                f"{t:%Y/%m/%d %H:%M:%S} "
                f"ALT={p[key].altitude.degrees:.1f}°"
            )

    max_i = max(
        range(len(alt)),
        key=lambda i: alt[i]
    )

    plt.annotate(
        f"MAX ALT\n{times[max_i].strftime('%H:%M:%S')}",
        (az[max_i], alt[max_i]),
        xytext=(20,20),
        textcoords="offset points"
    )

    plt.xlabel("Azimuth (deg)")
    plt.ylabel("Altitude (deg)")
    plt.title(
        f"ISS Pass {args.simulate_time}"
    )

    plt.xlim(0,360)
    plt.ylim(-5,90)

    plt.grid()

    plt.show()


if __name__ == "__main__":
    main()