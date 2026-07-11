import argparse
import time
from datetime import datetime, timedelta, timezone
import traceback

from core.ascom import ASCOMTelescope, MountSimulator
from core.astronomy import OrbitCalculator, TLELoader
from core.tracking import Guider, GuiderConfig, ISSTracker, TrackingConfig
from utils.planet import get_object_coordinates

import threading
import msvcrt

JST = timezone(timedelta(hours=9))

# テスト実行時
# python main.py --allow-network --duration 60 --align-object venus --simulate-time "2026/07/13 18:17:00"

# 実機実行
# python main.py --allow-network --duration 300 --align-object venus


def parse_args():
    parser = argparse.ArgumentParser(description="ISS tracker for E-ZEUS II (ASCOM)")
    parser.add_argument(
        "--mount",
        choices=["simulate", "ascom"],
        default="ascom",
        help="使用する架台。実機は ascom",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=300.0,
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

    parser.add_argument(
        "--time-offset",
        type=float,
        default=0.0,
        help="追尾開始時刻のオフセット [秒]",
    )
    parser.add_argument(
        "--simulate-time",
        type=str,
        default=None,
        help="シミュレーション開始時刻 (YYYY/MM/DD HH:MM:SS, JST)",
    )

    parser.add_argument(
        "--force-reload",
        action="store_true",
        help="TLEを強制的に再読み込み",
    )

    parser.add_argument(
        "--align-object",
        type=str,
        default=None,
        choices=[
            "sun",
            "moon",
            "mercury",
            "venus",
            "mars",
            "jupiter",
            "saturn",
            "uranus",
            "neptune",
        ],
        help="初期アライメントを行った天体。追尾終了後はこの天体へ戻る。",
    )

    return parser.parse_args()


def build_mount(kind: str):
    if kind == "ascom":
        return ASCOMTelescope()
    return MountSimulator()


def keyboard_loop(tracker):
    print(
        "\n=== Keyboard ===\n"
        "[←] または A : -0.1 s\n"
        "[→] または D : +0.1 s\n"
        "[Z]          : -1.0 s\n"
        "[C]          : +1.0 s\n"
        "[Q]          : 終了\n"
    )

    while tracker.is_tracking:
        if not msvcrt.kbhit():
            time.sleep(0.05)
            continue

        key = msvcrt.getch()

        # 矢印キー
        if key == b'\xe0':
            key = msvcrt.getch()

            if key == b'K':      # ←
                tracker.adjust_offset(-0.1)

            elif key == b'M':    # →
                tracker.adjust_offset(+0.1)

        else:
            key = key.lower()

            if key == b'a':
                tracker.adjust_offset(-0.1)

            elif key == b'd':
                tracker.adjust_offset(+0.1)

            elif key == b'z':
                tracker.adjust_offset(-1.0)

            elif key == b'c':
                tracker.adjust_offset(+1.0)

            elif key == b'q':
                tracker.stop_tracking()
                break


def main():
    args = parse_args()

    # TLE
    tle = TLELoader()
    tle.update(
        local_path=args.tle_file,
        allow_network=args.allow_network,
        force_reload=args.force_reload,
    )

    orbit = OrbitCalculator(tle.satellite)

    mount = build_mount(args.mount)
    mount.connect()

    try:

        try:
            mount_pos = mount.get_position()
            print(
                f"Mount now: RA={mount_pos.ra_hours:.4f}h "
                f"Dec={mount_pos.dec_degrees:.4f}°"
            )
        except Exception:
            mount_pos = None
            print("Mount now: Unknown")


        ####################################
        # 開始時刻
        ####################################

        if args.simulate_time is None:

            track_start = (
                datetime.now(timezone.utc)
                + timedelta(seconds=args.start_in)
            )

            wait = (
                track_start
                - datetime.now(timezone.utc)
            ).total_seconds()

            if wait > 0:
                print(f"Start in {wait:.1f}s")
                time.sleep(wait)

        else:

            track_start = (
                datetime.strptime(
                    args.simulate_time,
                    "%Y/%m/%d %H:%M:%S",
                )
                .replace(tzinfo=JST)
                .astimezone(timezone.utc)
            )

            print(
                "Simulation Time:",
                track_start.astimezone(JST).strftime(
                    "%Y/%m/%d %H:%M:%S JST"
                ),
            )

        print(
            "Tracking time:",
            track_start.astimezone(JST).strftime(
                "%Y/%m/%d %H:%M:%S JST"
            ),
        )

        ####################################
        # アライメント天体保存
        ####################################

        align_ra = None
        align_dec = None

        if args.align_object is not None:

            align_ra, align_dec = get_object_coordinates(
                args.align_object,
                orbit,
                track_start,
            )

            print(
                f"{args.align_object} : "
                f"RA={align_ra:.4f}h "
                f"Dec={align_dec:.4f}°"
            )

            print(
                f"\n{args.align_object} が視野中央にあることを確認してください。"
            )
            input("Enterキーで位置合わせ（Sync）を実行します...")

            mount.sync_to_coordinates(
                align_ra,
                align_dec,
            )

            mount_pos = mount.get_position()

            print(
                f"Sync後: "
                f"RA={mount_pos.ra_hours:.4f}h "
                f"Dec={mount_pos.dec_degrees:.4f}°"
            )

            print("RA =", mount.scope.RightAscension)
            print("Dec =", mount.scope.Declination)

            try:
                print("TargetRA =", mount.scope.TargetRightAscension)
                print("TargetDec =", mount.scope.TargetDeclination)
            except Exception as e:
                print(e)

        ####################################
        # Tracker
        ####################################

        guider = Guider(
            mount,
            GuiderConfig(),
        )

        tracking_config = TrackingConfig()
        tracking_config.pulse_interval_sec = args.interval

        tracker = ISSTracker(
            mount=mount,
            orbit=orbit,
            guider=guider,
            config=tracking_config,
        )

        tracker.set_offset(args.time_offset)

        ####################################
        # ISS導入
        ####################################

        tracker.acquire(track_start)

        if args.acquire_only:
            return

        keyboard_thread = threading.Thread(
            target=keyboard_loop,
            args=(tracker,),
            daemon=True,
        )

        keyboard_thread.start()

        ####################################
        # ISS追尾
        ####################################

        tracker.start_tracking(
            start_time=track_start,
            duration_sec=args.duration,
        )

        ####################################
        # アライメント天体へ戻る
        ####################################

        if align_ra is not None:

            print(
                f"\nReturning to {args.align_object}..."
            )

            mount.slew_to_coordinates(
                align_ra,
                align_dec,
                async_=True,
            )

            mount.wait_slew()

            print("Finished.")

    # except Exception as e:
    #     print(e)

    except Exception:
        traceback.print_exc()

    finally:
        mount.disconnect()


if __name__ == "__main__":
    main()