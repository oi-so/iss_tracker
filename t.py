"""
高速クラスの「立ち上がり時間（加速時間）」検証スクリプト

目的:
    tick_sec (ON時間の長さ) を短くすると、モーターが目標速度に達する前に
    次のOFFが来てしまい、実効速度が落ちるのではないか、という仮説の検証。

重要: 前回のテストが極付近(Dec≈90°)で行われてしまい、座標の折り返し
    (Dec>90でRA+12h, Dec=180-Dec に折り畳まれる)により速度計算が
    無効になっていた。このテストは必ず極から十分離れた場所
    (例: Dec 0-40°程度、前回の低速域キャリブレーションと同じような高度)
    で実行すること。

手順:
    1. まず現在位置を確認し、Dec が SAFE_DEC_MAX 以下であることを確認する
       (念のためコード内でもチェックし、危険なら中断する)
    2. 同じrate(高速クラス相当、例0.2)を、様々なON時間で繰り返し実行し、
       「ON時間 × 回数の合計」に対する実際の移動量から実効速度を算出する
    3. ON時間を変えたときに実効速度がどう変化するかを見る
       -> 短いON時間ほど実効速度が下がるなら、加速時間の影響が大きいと言える
"""

import time

from core.ascom.telescope import ASCOMTelescope


SAFE_DEC_MAX = 60.0  # これを超える(極に近い)場所では危険なので実行しない
HIGH_RATE = 0.15      # 高速クラスに入る値（前回確認したhigh classの範囲内）
N_REPEATS = 20        # 同じON時間を何回繰り返すか(平均を取って再現性を見る)

# 検証したいON時間のバリエーション（秒）
ON_TIMES = [0.01, 0.02, 0.05, 0.1, 0.5, 2.0]


def wait_settled(mount, axis, poll_interval=0.05, settle_time=0.5, timeout=5.0):
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


def measure_burst_efficiency(mount, axis, rate, on_time, n_repeats):
    """
    on_time 秒だけ move_axis(axis, rate) -> move_axis(axis, 0) を
    n_repeats 回繰り返し、その合計ON時間に対する実際の移動量から
    実効速度を計算する。

    もし加速時間の影響が大きいなら、on_timeが短いほど
    「実効速度 / HIGH相当の定常速度」の比率が下がるはずである。

    テスト後は必ず元の位置に戻す(逆方向に同じ手順で駆動して戻す)。
    これをしないと、テストを繰り返すたびに位置がどんどんずれていき、
    長いon_timeのテストほど極に近づいてしまう(実際に発生した問題)。
    """
    wait_settled(mount, axis)
    pos_before = mount.get_position()
    t0 = time.perf_counter()

    delta = 0.0
    for _ in range(n_repeats):
        mount.move_axis(axis, rate)
        time.sleep(on_time)
        mount.move_axis(axis, 0)
        # OFF時間はON時間と同程度取り、モーターが完全停止する時間も確保する
        time.sleep(on_time)
        wait_settled(mount, axis)
        pos_after = mount.get_position()
        if axis == 0:
            delta += (pos_after.ra_hours - pos_before.ra_hours) * 15
        else:
            delta += pos_after.dec_degrees - pos_before.dec_degrees
        # 元の位置にgotoで戻す
        if abs(pos_after.ra_hours - pos_before.ra_hours) > 0.1 or abs(pos_after.dec_degrees - pos_before.dec_degrees) > 1:
            mount.slew_to_coordinates(pos_before.ra_hours, pos_before.dec_degrees)
    
    mount.slew_to_coordinates(pos_before.ra_hours, pos_before.dec_degrees)


    # ON時間の合計に対する実効速度（OFF時間中は動かない前提）
    total_on_time = on_time * n_repeats
    effective_rate = delta / total_on_time if total_on_time else 0.0

    print(
        f"on_time={on_time:5.2f}s x{n_repeats:2d}回 "
        f"合計ON時間={total_on_time:5.2f}s "
        f"移動量={delta:+.4f}deg "
        f"実効速度(ON時間ベース)={effective_rate:+.4f}deg/s"
    )

    return effective_rate


def main():
    mount = ASCOMTelescope()
    mount.connect()

    try:
        pos = mount.get_position()
        print(f"現在位置: RA={pos.ra_hours:.4f}h Dec={pos.dec_degrees:.4f}°")

        if abs(pos.dec_degrees) > SAFE_DEC_MAX:
            print(
                f"⚠ Dec={pos.dec_degrees:.2f}° は極に近すぎます "
                f"(SAFE_DEC_MAX={SAFE_DEC_MAX}°)。"
                f"安全な高度に手動でSlewしてから再実行してください。"
            )
            return


        print("\n===== 高速クラスのON時間ごとの実効速度 (RA軸) =====")
        for on_time in ON_TIMES:
            measure_burst_efficiency(mount, axis=0, rate=HIGH_RATE, on_time=on_time, n_repeats=N_REPEATS)
            time.sleep(1)
        print("\n===== 高速クラスのON時間ごとの実効速度 (Dec軸) =====")
        for on_time in ON_TIMES:
            measure_burst_efficiency(mount, axis=1, rate=HIGH_RATE, on_time=on_time, n_repeats=N_REPEATS)
            time.sleep(1)

    finally:
        mount.move_axis(0, 0)
        mount.move_axis(1, 0)
        mount.disconnect()


if __name__ == "__main__":
    main()