"""
E-ZEUS II 追加キャリブレーションスクリプト (v2)

これまでの実機テストで判明していること（Dec軸 / axis=1）:
    - rate < 0.06          -> 実質無反応（ノイズフロア 約0.004-0.005 deg/s）
    - 0.06 <= rate <= 0.065 -> 低速クラス、実測 約0.079-0.080 deg/s
    - rate >= 0.067        -> 高速クラス、実測 約0.70-0.72 deg/s

今回の追加テストで確認したいこと:
    1. RA軸（axis=0）でも同じ3クラス構造か、対称かどうか
    2. 高速クラスのさらに先（SUPERSTAR IVで感じた"もっと速い"速度）があるか
       -> 安全のため duration を短くし、位置変化量が大きくなりすぎないよう
          事前に小さい値から段階的に上げる
    3. 低速クラスの下限境界（0.05-0.06付近）をもっと細かく特定

出力は画面表示に加えて CSV (calibration_result.csv) にも保存します。
後で pandas 等でグラフ化しやすいように、生の delta / duration も記録します。

安全に関する注意:
    - 高速テスト (0.2 deg/s 以上) を行う前に、望遠鏡の可動範囲・ケーブルの取り回し・
      三脚や周辺機材との干渉がないか目視確認してから実行してください。
    - 高速クラス実測値(前回 Dec軸で約0.71 deg/s)を踏まえ、
      HIGH_SPEED_DURATION は短め(2秒程度)に設定してあります。
      2秒 * 2.0 deg/s = 4度 程度の移動に収まる想定ですが、
      不安な場合は HIGH_SPEED_TEST_RATES を減らす/コメントアウトしてください。
    - 各テストの前後で wait_settled により静止を確認してから次に進みます。
    - Ctrl+C で安全に中断できるよう、KeyboardInterrupt 時に停止コマンドを送ります。
"""

import csv
import time
from datetime import datetime

from core.ascom.telescope import ASCOMTelescope


CSV_PATH = "calibration_result.csv"

# ---- 通常速度域テストで使う値 ----
LOW_CLASS_PROBE_RATES = [0.003, 0.0042, 0.02, 0.033]
BOUNDARY_3_4_RATES = [0.06, 0.065, 0.067, 0.07, 0.08, 0.09]
REPEAT_RATE = 0.15
REPEAT_COUNT = 5
NEGATIVE_RATES = [-0.05, -0.10, -0.15]

# ---- 0.05-0.06 境界の絞り込み用（追加） ----
FINE_BOUNDARY_RATES = [0.050, 0.052, 0.054, 0.055, 0.056, 0.057, 0.058, 0.059, 0.060]

# ---- 高速域の存在確認用（追加・要注意） ----
# 小さい値から徐々に上げていき、途中で明らかにおかしければ手動で中断してください
HIGH_SPEED_TEST_RATES = [0.2, 0.3, 0.5, 1.0, 1.5, 2.0]
HIGH_SPEED_DURATION = 2.0  # 秒。速いので短めに

NORMAL_DURATION = 5.0
LOW_CLASS_DURATION = 5.0

results = []


def log_result(axis, rate, actual_rate, duration):
    ratio = actual_rate / rate if rate else 0.0
    print(
        f"axis={axis} 指令rate={rate:+.4f}deg/s "
        f"実測rate={actual_rate:+.4f}deg/s "
        f"倍率={ratio:+.2f}x duration={duration:.1f}s"
    )
    results.append(
        {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "axis": axis,
            "commanded_rate": rate,
            "actual_rate": actual_rate,
            "ratio": ratio,
            "duration_sec": duration,
        }
    )


def wait_settled(mount, axis, poll_interval=0.1, settle_time=1.0, timeout=8.0):
    """位置が一定時間変化しなくなるまで待つ"""
    start = time.time()
    last_pos = None
    stable_since = None

    while time.time() - start < timeout:
        pos = mount.get_position()
        val = pos.ra_hours if axis == 0 else pos.dec_degrees
        if last_pos is not None and abs(val - last_pos) < 1e-5:
            if stable_since is None:
                stable_since = time.time()
            elif time.time() - stable_since > settle_time:
                return
        else:
            stable_since = None
        last_pos = val
        time.sleep(poll_interval)
    # タイムアウトしても致命的ではないので警告のみ
    print(f"  ⚠ wait_settled timeout (axis={axis})")


def calibrate_rate(mount, axis, rate, duration_sec=5.0):
    wait_settled(mount, axis)
    pos_before = mount.get_position()

    mount.move_axis(axis, rate)
    time.sleep(duration_sec)
    mount.move_axis(axis, 0)

    wait_settled(mount, axis)
    pos_after = mount.get_position()

    if axis == 0:
        delta = (pos_after.ra_hours - pos_before.ra_hours) * 15  # h -> deg
    else:
        delta = pos_after.dec_degrees - pos_before.dec_degrees

    actual_rate = delta / duration_sec
    log_result(axis, rate, actual_rate, duration_sec)
    return actual_rate


def test_move_axis_latency(mount, axis=1, rate=0.15, n=50):
    t0 = time.perf_counter()
    for _ in range(n):
        mount.move_axis(axis, rate)
        mount.move_axis(axis, 0)
    t1 = time.perf_counter()
    avg_ms = ((t1 - t0) / n) * 1000
    print(f"MoveAxis 1往復あたり平均 {avg_ms:.2f} ms (axis={axis})")
    return avg_ms


def run_axis_suite(mount, axis, include_high_speed=True):
    print(f"\n===== axis={axis} 通常域テスト =====")
    for r in LOW_CLASS_PROBE_RATES:
        calibrate_rate(mount, axis, r, duration_sec=LOW_CLASS_DURATION)
        time.sleep(1)

    print(f"\n===== axis={axis} class3/4境界（粗）=====")
    for r in BOUNDARY_3_4_RATES:
        calibrate_rate(mount, axis, r, duration_sec=NORMAL_DURATION)
        time.sleep(1)

    print(f"\n===== axis={axis} 再現性確認 (rate={REPEAT_RATE}) =====")
    for _ in range(REPEAT_COUNT):
        calibrate_rate(mount, axis, REPEAT_RATE, duration_sec=NORMAL_DURATION)
        time.sleep(1)

    print(f"\n===== axis={axis} 負方向 =====")
    for r in NEGATIVE_RATES:
        calibrate_rate(mount, axis, r, duration_sec=NORMAL_DURATION)
        time.sleep(1)

    print(f"\n===== axis={axis} 0.05-0.06 境界の絞り込み（追加）=====")
    for r in FINE_BOUNDARY_RATES:
        calibrate_rate(mount, axis, r, duration_sec=NORMAL_DURATION)
        time.sleep(1)

    if include_high_speed:
        print(f"\n===== axis={axis} 高速域の存在確認（追加・注意）=====")
        print("周辺に障害物がないか確認してください。5秒後に開始します...")
        time.sleep(5)
        for r in HIGH_SPEED_TEST_RATES:
            calibrate_rate(mount, axis, r, duration_sec=HIGH_SPEED_DURATION)
            time.sleep(2)


def save_csv(path):
    if not results:
        return
    fieldnames = list(results[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    print(f"\n結果を {path} に保存しました（{len(results)}件）")


def main():
    mount = ASCOMTelescope()
    mount.connect()

    try:
        # Dec軸(axis=1)は前回大部分やっているので、
        # 今回重点的に見たい「高速域の先」と「0.05-0.06境界」を優先。
        # 必要なければ include_high_speed=False や
        # run_axis_suite の呼び出し自体をコメントアウトしてください。
        run_axis_suite(mount, axis=1, include_high_speed=True)

        # RA軸は今回ほぼ未実施なので、通常域からまとめて実施
        run_axis_suite(mount, axis=0, include_high_speed=True)

        test_move_axis_latency(mount, axis=1)
        test_move_axis_latency(mount, axis=0)

    except KeyboardInterrupt:
        print("\n中断されました。安全のため両軸を停止します。")
        try:
            mount.move_axis(0, 0)
            mount.move_axis(1, 0)
        except Exception as e:
            print(f"停止コマンド送信エラー: {e}")

    finally:
        # save_csv(CSV_PATH)
        mount.disconnect()


if __name__ == "__main__":
    main()