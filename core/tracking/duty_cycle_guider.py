"""
離散速度クラス対応ガイダー (DutyCycleGuider)

E-ZEUS IIのMoveAxisが連続可変ではなく離散的な速度クラスにスナップすることを
前提に、必要な平均角速度を「固定速度でのON/OFF比率(duty cycle)」で近似する。

既存の MoveAxisGuider (core/tracking/move_axis_guider.py) を置き換える形で
使う想定。ISSTracker 側からの呼び出しインターフェース(guide/stop)は変えていない
ので、tracker.py 側の変更は基本的にガイダーの差し替えだけで済む。

RA/Dec 2軸を同じガイド周期 (pulse_interval_sec) の中で並行して
ON/OFF制御するため、周期をさらに細かい tick に分割し、
各 tick で「RAは今ONにすべきか」「Decは今ONにすべきか」を
duty比の累積誤差(いわゆるBresenham的な考え方)で判定している。
"""

from __future__ import annotations

from dataclasses import dataclass
import time

from core.tracking.guider import Guider
from .discrete_rate import RATE_TABLE, DiscreteRateMapper, RateClass


@dataclass
class DutyCycleConfig:
    """DutyCycleGuider の設定。

    kp:               位置誤差に対する比例ゲイン (MoveAxisConfigのkpと同じ意味)
    dead_band_deg:    この誤差以下は補正しない不感帯
    velocity_scale:   ISS角速度に対する補正倍率。1.0から始めて実測で追い込む。
    tick_sec:         duty比を実現するための内部分割周期。
                      pulse_interval_sec (通常0.1s) をさらに割った値。
                      小さいほど滑らかだが、COM呼び出し回数が増える。
                      MoveAxis呼び出しは実測0.46ms/往復程度なので、
                      0.01s (10ms) 程度までは十分現実的。
    hysteresis:       DiscreteRateMapper に渡すヒステリシス幅。
    """

    kp: float = 0.15
    dead_band_deg: float = 0.0005
    velocity_scale: float = 1.0
    tick_sec: float = 0.02
    hysteresis: float = 0.1
    pulse_interval_sec: float = 0.1


class _AxisDutyState:
    """1軸分のduty制御状態。累積誤差方式でON/OFFタイミングを決める。"""

    def __init__(self):
        self.accumulator: float = 0.0

    def should_be_on(self, duty: float) -> bool:
        """今回のtickでONにすべきかを、累積誤差方式で判定する。

        duty=0.3 なら、10回のtickのうち平均して3回ONになるように、
        誤差を持ち越しながら判定する（単純な間引きより滑らかになる）。
        """
        self.accumulator += duty
        if self.accumulator >= 1.0:
            self.accumulator -= 1.0
            return True
        return False

    def reset(self):
        self.accumulator = 0.0


class DutyCycleGuider(Guider):
    """離散速度クラス+duty比制御によるガイダー。"""

    def __init__(self, mount, config: DutyCycleConfig | None = None):
        super().__init__(mount, config or DutyCycleConfig())

        self._mappers: dict[int, DiscreteRateMapper] = {
            axis: DiscreteRateMapper(table, hysteresis=self.config.hysteresis)
            for axis, table in RATE_TABLE.items()
        }
        self._duty_states: dict[int, _AxisDutyState] = {
            axis: _AxisDutyState() for axis in RATE_TABLE.keys()
        }
        # 各軸、直前にmove_axisへ送った値をキャッシュし、
        # 同じ値なら再送しない(不要なCOM呼び出しを削減)
        self._last_sent: dict[int, float] = {axis: 0.0 for axis in RATE_TABLE.keys()}

    def guide(
        self,
        ra_velocity_deg_per_sec: float,
        dec_velocity_deg_per_sec: float,
        ra_error_deg: float,
        dec_error_deg: float,
    ) -> None:
        """
        必要な平均速度を計算し、pulse_interval一周期分のduty制御を
        ここでブロッキング実行する（既存のISSTrackerのループ構造に合わせる）。

        呼び出し元(ISSTracker.start_tracking)は pulse_interval_sec ごとに
        このguide()を呼ぶ設計なので、ここで実際にそのpulse_interval_sec分の
        時間を消費してPWM制御を行う。
        """
        ra_rate = -(
            ra_velocity_deg_per_sec * self.config.velocity_scale
            + self.config.kp * ra_error_deg
        )  # RAは符号反転（既存実装に合わせる）
        dec_rate = (
            dec_velocity_deg_per_sec * self.config.velocity_scale
            + self.config.kp * dec_error_deg
        )

        if abs(ra_rate) < self.config.dead_band_deg:
            ra_rate = 0.0
        if abs(dec_rate) < self.config.dead_band_deg:
            dec_rate = 0.0

        ra_cls, ra_duty, ra_sign = self._mappers[0].compute_duty(ra_rate)
        dec_cls, dec_duty, dec_sign = self._mappers[1].compute_duty(dec_rate)

        self._run_pwm_cycle(
            cycle_sec=self._pulse_interval(),
            axis_plan={
                0: (ra_cls, ra_duty, ra_sign),
                1: (dec_cls, dec_duty, dec_sign),
            },
        )

    def _pulse_interval(self) -> float:
        """呼び出し元のpulse_interval_secを使いたいが、Guiderは
        TrackingConfigを直接持たないため、tick_secの整数倍として
        ここでは固定値を使う。tracker側のpulse_interval_secと
        一致させたい場合は、DutyCycleConfigに持たせて渡すこと。
        """
        return getattr(self.config, "pulse_interval_sec", 0.1)

    def _run_pwm_cycle(
        self,
        cycle_sec: float,
        axis_plan: dict[int, tuple[RateClass | None, float, int]],
    ) -> None:
        tick = self.config.tick_sec
        n_ticks = max(1, round(cycle_sec / tick))
        actual_tick = cycle_sec / n_ticks

        for _ in range(n_ticks):
            for axis, (cls, duty, sign) in axis_plan.items():
                state = self._duty_states[axis]

                if cls is None or duty <= 0.0:
                    self._send_rate(axis, 0.0)
                    state.reset()
                    continue

                if state.should_be_on(duty):
                    # self._send_rate(axis, sign * cls.actual_rate)
                    input_rate = self._mappers[axis].table.input_for_class(cls)
                    self._send_rate(axis, sign * input_rate)
                else:
                    self._send_rate(axis, 0.0)

            time.sleep(actual_tick)

        # 周期の終わりには必ず両軸停止しておく
        for axis in axis_plan.keys():
            self._send_rate(axis, 0.0)

    def _send_rate(self, axis: int, rate: float) -> None:
        """前回と同じ値なら再送しない。"""
        if self._last_sent[axis] == rate:
            return
        self.mount.move_axis(axis, rate)
        self._last_sent[axis] = rate

    def reset_mappers(self) -> None:
        """reacquire(再導入)直後など、ヒステリシス状態をリセットしたい時に呼ぶ。"""
        for mapper in self._mappers.values():
            mapper.reset()
        for state in self._duty_states.values():
            state.reset()

    def stop(self) -> None:
        self.mount.move_axis(0, 0)
        self.mount.move_axis(1, 0)
        self._last_sent = {axis: 0.0 for axis in self._last_sent}
        self.reset_mappers()