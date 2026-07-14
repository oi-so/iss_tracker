from core.tracking.guider import Guider

import time
from dataclasses import dataclass


@dataclass(frozen=True)
class RateClassSpec:
    """1つの固定速度クラスの実測データ。

    name:        識別用の名前
    input_min:   このクラスを選ぶために MoveAxis へ渡してよい入力の下限 (deg/s)
    input_max:   同上、上限（ドライバの申告レンジと一致させる）
    actual_rate: このクラスで実際に動く速度 (deg/s)。calibrate_rate.py の
                 実測結果をそのまま転記する。duty比の計算にのみ使う
                 （MoveAxisへは safe_input を渡すので、ここが多少不正確でも
                 クラッシュはしない。ズレが大きいと平均速度の誤差になるだけ）。
    """

    name: str
    input_min: float
    input_max: float
    actual_rate: float

    @property
    def safe_input(self) -> float:
        """MoveAxisへ実際に渡す入力値。レンジの中央値を使う。"""
        return (self.input_min + self.input_max) / 2.0


class MoveAxisConfig:
    kp = 0.15
    velocity_scale = 1.15  # ISS角速度に対する補正倍率
    dead_band_deg = 0.0005

    MAX_SAFE_INPUT = 0.208904  # ドライバ申告上限。これを超えると例外でクラッシュする

    tick_sec = 0.02
    hysteresis = 0.1

    # 軸ごとの実測済み速度クラス一覧。
    # ※ "fastest" は rate=0.2 の1点のみの測定(duration=2.0秒、短時間)から
    #    仮定したもの。0.2秒付近のみ実測しており、この境界(0.195など)は
    #    未確定。将来 duration=5.0秒程度で再測定し、
    #    - "high"と同じ約0.70に収束するなら fastest は削除してよい
    #    - 別の値(約0.43)に安定するなら、境界をもっと絞り込むこと
    CLASSES: dict[int, tuple[RateClassSpec, ...]] = {
        0: (  # RA軸: 仮置き（Dec軸と同値、fastestも含め要実測）
            RateClassSpec(name="low", input_min=0.033426, input_max=0.066849, actual_rate=0.080),
            RateClassSpec(name="high", input_min=0.066850, input_max=0.194999, actual_rate=0.700),
            RateClassSpec(name="fastest", input_min=0.195000, input_max=0.208904, actual_rate=0.4332),
        ),
        1: (  # Dec軸: low/highは実測済み、fastestは仮説段階
            RateClassSpec(name="low", input_min=0.033426, input_max=0.066849, actual_rate=0.080),
            RateClassSpec(name="high", input_min=0.066850, input_max=0.194999, actual_rate=0.700),
            RateClassSpec(name="fastest", input_min=0.195000, input_max=0.208904, actual_rate=0.4332),
        ),
    }

    def classes_for(self, axis: int) -> tuple:
        return tuple(sorted(self.CLASSES[axis], key=lambda c: c.actual_rate))



# class MoveAxisConfig:
#     """
#     2026/07 実機キャリブレーションで判明したこと:

#         ドライバは4つのレート範囲を申告するが、実際に意味のある動きを
#         するのは以下の2クラスのみだった:
#             "low"  : 入力 0.033426-0.066849 -> 実測 約0.080 deg/s
#             "high" : 入力 0.066850-0.208904 -> 実測 約0.70  deg/s

#         0.002089-0.033425 の範囲は実測でほぼ無反応（ノイズフロア以下）。

#         申告上限 0.208904 を1つでも超える値を MoveAxis に渡すと、
#         ドライバが InvalidValueException を投げてクラッシュすることを
#         実機で確認済み（SUPERSTAR IVのハンドコントローラで感じる
#         「もっと速い」動きは、GOTO専用の別系統コマンドによるものと考えられ、
#         現状 MoveAxis 経由ではアクセスできない可能性が高い）。

#     もし将来、別の入力の与え方や設定変更で「最速クラス」が見つかった場合は、
#     CLASSES のタプルに1行追加するだけでよい。例えば実測で1.5deg/s級の
#     クラスが見つかったなら:

#         RateClassSpec(name="fastest", input_min=?, input_max=?, actual_rate=1.5),

#     を追加すればよい（並び順は自動でソートされるので気にしなくてよい）。
#     ただし、そのクラスの input_max がドライバの実際の申告上限を
#     超えないことを、事前に AxisRates() で必ず確認すること。
#     """

#     kp = 0.15
#     velocity_scale = 1.15  # ISS角速度に対する補正倍率。要実測で再調整。
#     dead_band_deg = 0.0005

#     # ドライバが実際に InvalidValueException を投げずに受け付ける絶対上限。
#     # これを1つでも超える値は絶対に MoveAxis へ渡さないこと（実機で確認済み）。
#     MAX_SAFE_INPUT = 0.208904

#     # duty比制御の内部分割周期。pulse_interval_sec をこの値でさらに分割する。
#     # MoveAxis呼び出しは実測0.46ms/往復程度なので、0.02s程度までは現実的。
#     tick_sec = 0.02

#     # クラス切り替えのヒステリシス幅(0.0-1.0)。境界付近での頻繁な
#     # クラス切り替え(チャタリング)を防ぐため、現在使用中のクラスの
#     # 実効範囲を +- この割合だけ広げて判定する。
#     hysteresis = 0.1

#     # 軸ごとの実測済み速度クラス一覧。
#     # RA(axis=0) はまだ個別実測が途中のため、Dec(axis=1)と同じ値を仮置きしている。
#     # RA軸の実測が完了したら、axis=0側だけ書き換えること。
#     CLASSES: dict[int, tuple[RateClassSpec, ...]] = {
#         0: (  # RA軸: 仮置き（Dec軸と同値）
#             RateClassSpec(name="low", input_min=0.033426, input_max=0.066849, actual_rate=0.080),
#             RateClassSpec(name="high", input_min=0.066850, input_max=0.208904, actual_rate=0.700),
#             # RateClassSpec(name="fastest", input_min=?, input_max=?, actual_rate=?),
#         ),
#         1: (  # Dec軸: 実測済み
#             RateClassSpec(name="low", input_min=0.033426, input_max=0.066849, actual_rate=0.080),
#             RateClassSpec(name="high", input_min=0.066850, input_max=0.208904, actual_rate=0.700),
#             # RateClassSpec(name="fastest", input_min=?, input_max=?, actual_rate=?),
#         ),
#     }

#     def classes_for(self, axis: int) -> tuple[RateClassSpec, ...]:
#         """速度の遅い順にソートして返す。"""
#         return tuple(sorted(self.CLASSES[axis], key=lambda c: c.actual_rate))


class _AxisDutyState:
    """1軸分のduty制御状態。累積誤差方式でON/OFFタイミングを決める
    (いわゆるBresenham的な考え方。単純な間引きより平均速度が滑らかになる)。
    """

    def __init__(self):
        self.accumulator: float = 0.0
        self.current_class: RateClassSpec | None = None

    def should_be_on(self, duty: float) -> bool:
        self.accumulator += duty
        if self.accumulator >= 1.0:
            self.accumulator -= 1.0
            return True
        return False

    def reset(self):
        self.accumulator = 0.0
        self.current_class = None


class MoveAxisGuider(Guider):

    def __init__(self, mount, config=None, pulse_interval_sec: float = 0.1):
        super().__init__(mount, config or MoveAxisConfig())
        self.pulse_interval_sec = pulse_interval_sec

        self._classes = {
            axis: self.config.classes_for(axis) for axis in self.config.CLASSES
        }
        self._states: dict[int, _AxisDutyState] = {
            axis: _AxisDutyState() for axis in self.config.CLASSES
        }
        self._last_sent: dict[int, float] = {axis: 0.0 for axis in self.config.CLASSES}

    def guide(
        self,
        ra_velocity_deg_per_sec,
        dec_velocity_deg_per_sec,
        ra_error_deg,
        dec_error_deg,
    ):
        """
        ISS角速度を基本速度として、位置誤差による補正を少量加えた
        「欲しい平均速度」を計算し、pulse_interval_sec一周期分の
        duty比制御をブロッキングで実行する。

        MoveAxisが連続可変ではなく離散的な速度クラスにしか対応していない
        ため、必要な平均速度をそのまま送るのではなく、
        「どのクラスを使い、どれくらいの時間比率でON/OFFすれば
        平均としてその速度に近づくか」に変換してから送信する。
        """

        ra_rate = ra_velocity_deg_per_sec * self.config.velocity_scale + self.config.kp * ra_error_deg
        dec_rate = dec_velocity_deg_per_sec * self.config.velocity_scale + self.config.kp * dec_error_deg

        if abs(ra_rate) < self.config.dead_band_deg:
            ra_rate = 0.0
        if abs(dec_rate) < self.config.dead_band_deg:
            dec_rate = 0.0

        # RA方向は符号反転（現在の赤道儀設定に合わせる。既存実装を踏襲）
        plan = {
            0: self._plan_for_axis(0, -ra_rate),
            1: self._plan_for_axis(1, dec_rate),
        }

        self._run_pwm_cycle(plan)

    def _plan_for_axis(self, axis: int, desired_rate: float):
        """desired_rate から (使用するクラス, duty比, sign) を決める。
        ヒステリシス付き: 直前に使っていたクラスの実効範囲内であれば
        同じクラスを維持し、境界付近での細かい切り替えを防ぐ。
        """
        sign = 1 if desired_rate >= 0 else -1
        mag = abs(desired_rate)
        classes = self._classes[axis]
        state = self._states[axis]

        if mag < 1e-4 or not classes:
            state.current_class = None
            return None, 0.0, sign

        chosen = self._select_class(classes, state, mag)

        if chosen is None:
            # どのクラスの実効速度でも足りない -> 一番速いクラスで頭打ち
            chosen = classes[-1]
            duty = 1.0
        else:
            duty = min(mag / chosen.actual_rate, 1.0)

        state.current_class = chosen
        return chosen, duty, sign

    def _select_class(self, classes, state: _AxisDutyState, mag: float):
        if state.current_class is not None:
            idx = classes.index(state.current_class)
            lower_bound = (
                classes[idx - 1].actual_rate * (1 + self.config.hysteresis) if idx > 0 else 0.0
            )
            upper_bound = state.current_class.actual_rate * (1 + self.config.hysteresis)
            if lower_bound <= mag <= upper_bound:
                return state.current_class

        for cls in classes:
            if mag <= cls.actual_rate:
                return cls
        return None

    def _run_pwm_cycle(self, plan: dict):
        n_ticks = max(1, round(self.pulse_interval_sec / self.config.tick_sec))
        actual_tick = self.pulse_interval_sec / n_ticks

        for _ in range(n_ticks):
            for axis, (cls, duty, sign) in plan.items():
                state = self._states[axis]

                if cls is None or duty <= 0.0:
                    self._send_rate(axis, 0.0)
                    continue

                if state.should_be_on(duty):
                    # 重要: MoveAxisへは実測速度(actual_rate)ではなく、
                    # そのクラスを選ぶための入力値(safe_input)を渡す。
                    # 実測速度をそのまま渡すとドライバの申告上限を超えて
                    # InvalidValueExceptionでクラッシュする(実機で確認済み)。
                    self._send_rate(axis, sign * cls.safe_input)
                else:
                    self._send_rate(axis, 0.0)

            time.sleep(actual_tick)

        for axis in plan.keys():
            self._send_rate(axis, 0.0)

    def _send_rate(self, axis: int, rate: float):
        # 安全のため、万一にも申告上限を超える値は絶対に送らない
        rate = max(-self.config.MAX_SAFE_INPUT, min(self.config.MAX_SAFE_INPUT, rate))

        if self._last_sent[axis] == rate:
            return
        try:
            self.mount.move_axis(axis, rate)
            self._last_sent[axis] = rate
        except RuntimeError as e:
            print(f"⚠ move_axis失敗 (axis={axis}, rate={rate:.4f}): {e}")
            self._last_sent[axis] = float("nan")  # 次回は必ず再送させる

    def stop(self):
        self.mount.move_axis(0, 0)
        self.mount.move_axis(1, 0)
        self._last_sent = {axis: 0.0 for axis in self._last_sent}
        for state in self._states.values():
            state.reset()