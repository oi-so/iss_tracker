import argparse
import time
from datetime import datetime, timedelta, timezone

from core.ascom import ASCOMTelescope, MountSimulator
from core.astronomy import OrbitCalculator, TLELoader
from core.tracking import Guider, GuiderConfig, ISSTracker, TrackingConfig


def parse_args():
    parser = argparse.ArgumentParser(description="ISS tracker for E-ZEUS II (ASCOM)")
    parser.add_argument(
        "--mount",
        choices=["simulate", "ascom"],
        default="simulate",
        help="使用する架台。実機は ascom",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="追尾時間 [秒]",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=0.1,
        help="追尾周期 [秒]",
    )
    parser.add_argument(
        "--start-in",
        type=float,
        default=5.0,
        help="何秒後に導入開始するか [秒]",
    )
    parser.add_argument(
        "--tle-file",
        type=str,
        default="data/iss.tle",
        help="ローカルTLEファイルのパス",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help="ローカルTLEが無い場合にネット取得を許可",
    )
    parser.add_argument(
        "--acquire-only",
        action="store_true",
        help="導入だけ実行して終了",
    )
    return parser.parse_args()


def build_mount(kind: str):
    if kind == "ascom":
        return ASCOMTelescope()
    return MountSimulator()


def main():
    args = parse_args()

    # TLE / Orbit
    tle = TLELoader()
    tle.update(local_path=args.tle_file, allow_network=args.allow_network)
    orbit = OrbitCalculator(tle.satellite)

    # Mount
    mount = build_mount(args.mount)
    mount.connect()

    try:
        # 現在位置
        mount_pos = mount.get_position()
        print(
            f"Mount now: RA={mount_pos.ra_hours:.4f}h "
            f"Dec={mount_pos.dec_degrees:.4f}°"
        )

        # 追尾時刻
        track_start = datetime.now(timezone.utc) + timedelta(seconds=args.start_in)
        wait_sec = (track_start - datetime.now(timezone.utc)).total_seconds()
        if wait_sec > 0:
            print(f"Start in {wait_sec:.1f}s")
            time.sleep(wait_sec)

        # Tracker
        guider = Guider(mount, GuiderConfig())
        tracking_config = TrackingConfig()
        tracking_config.pulse_interval_sec = args.interval
        tracker = ISSTracker(mount=mount, orbit=orbit, guider=guider, config=tracking_config)

        # 導入
        tracker.acquire(track_start)

        if args.acquire_only:
            print("Acquire only 完了")
            return

        # 追尾
        tracker.start_tracking(start_time=track_start, duration_sec=args.duration)

    finally:
        mount.disconnect()


if __name__ == "__main__":
    main()