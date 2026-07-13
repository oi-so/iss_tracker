"""
離散速度クラスの定義とマッピングロジック

E-ZEUS IIのMoveAxisは連続可変速度ではなく、実測の結果、
入力値に応じて数段階の固定速度クラスにスナップすることが確認されている。

このファイルの役割は2つに分かれている:

    1. RATE_TABLE (下部) -- 実機キャリブレーションで得られた「生の事実」を
       書くだけの場所。ロジックは一切含まない。実機で再測定するたびに
       ここだけ書き換えればよい。

    2. DiscreteRateMapper -- RATE_TABLE を使って
       「欲しい平均角速度」→「どのクラスを使い、どれくらいのduty比で
       ON/OFFすればその平均速度に近づけるか」を計算するロジック。
       こちらはキャリブレーション値が変わっても書き換える必要がない。

使い方:
    mapper = DiscreteRateMapper(RATE_TABLE[0])  # axis=0 (RA)用
    cls, duty, sign = mapper.compute_duty(desired_rate=0.045)
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class RateClass:
    """1つの固定速度クラス。

    name:        表示用の名前 ("stop" / "low" / "high" / "superhigh" 等)
    actual_rate: このクラスで実際に動く速度 (deg/s, 正の値)。
                 calibrate_rate.py 等の実測結果からそのまま転記する。
    input_min:   このクラスが選ばれる MoveAxis への入力値の下限 (deg/s)。
                 config.axis_rates の各レンジの下限にあたる。
    input_max:   同上、上限。最上位クラスは実質使わないが一応入れておく。
    """

    name: str
    actual_rate: float
    input_min: float
    input_max: float


@dataclass(frozen=True)
class RateTable:
    """ある1軸についての、停止を除いた速度クラス一覧（速度の遅い順）。"""

    classes: tuple[RateClass, ...]

    def input_for_class(self, cls: RateClass) -> float:
        """そのクラスを選ぶために実際に MoveAxis へ渡す入力値。
        レンジの中央値あたりを使うと安全（境界ぎりぎりを避ける）。
        """
        return (cls.input_min + cls.input_max) / 2.0


# =====================================================================
# ここから下が「実測値を書くだけの場所」。
# 実機で再キャリブレーションしたら、この RATE_TABLE の中身だけ書き換える。
#
# axis=0 -> RA軸, axis=1 -> Dec軸
#
# 現時点(2026/07)でのDec軸実測値:
#   0.06-0.065   -> 実測 約0.079-0.080 deg/s (low)
#   0.067以上    -> 実測 約0.70-0.72   deg/s (high)
#   0.06未満     -> 無反応
#
# RA軸は未測定のため、いったんDec軸と同じ値を仮置きしている。
# RA軸の実測が出たら、以下の axis 0 の部分だけ書き換えること。
# 4段階目(superhigh)が見つかった場合は、classes のタプルに追加するだけでよい。
# =====================================================================

RATE_TABLE: dict[int, RateTable] = {
    # --- axis=0 (RA) : 仮置き。RA軸実測後に書き換えること ---
    0: RateTable(
        classes=(
            RateClass(name="low", actual_rate=0.080, input_min=0.060, input_max=0.065),
            RateClass(name="high", actual_rate=0.715, input_min=0.067, input_max=0.150),
        )
    ),
    # --- axis=1 (Dec) : 実測済み ---
    1: RateTable(
        classes=(
            RateClass(name="low", actual_rate=0.080, input_min=0.060, input_max=0.065),
            RateClass(name="high", actual_rate=0.715, input_min=0.067, input_max=0.150),
        )
    ),
}


class DiscreteRateMapper:
    """RateTable を使って、必要な平均速度からduty比を計算する。

    キャリブレーション値そのものには一切依存しないロジックのみを持つ。
    """

    def __init__(self, table: RateTable, hysteresis: float = 0.1):
        """
        Args:
            table: 対象軸のRateTable
            hysteresis: クラス切り替えのヒステリシス(0.0-1.0)。
                現在使用中のクラスの範囲を +-hysteresis 分だけ広げて判定し、
                境界付近での頻繁なクラス切り替え(チャタリング)を抑える。
        """
        # 速度の遅い順に並べておく
        self.classes = sorted(table.classes, key=lambda c: c.actual_rate)
        self.table = table
        self.hysteresis = hysteresis
        self._current_class: RateClass | None = None  # ヒステリシス用の状態

    def reset(self) -> None:
        """再導入(reacquire)直後など、状態をリセットしたいときに呼ぶ。"""
        self._current_class = None

    def compute_duty(self, desired_rate: float) -> tuple[RateClass | None, float, int]:
        """
        Args:
            desired_rate: 欲しい平均角速度 (deg/s, 符号あり)

        Returns:
            (使用する RateClass または None, duty比 0.0-1.0, sign +1/-1)
            None が返る場合は完全停止でよいことを意味する。
        """
        sign = 1 if desired_rate >= 0 else -1
        mag = abs(desired_rate)

        if not self.classes:
            return None, 0.0, sign

        if mag < 1e-4:
            self._current_class = None
            return None, 0.0, sign

        chosen = self._select_class(mag)

        if chosen is None:
            # 最速クラスの上限すら超える場合は頭打ち
            chosen = self.classes[-1]
            duty = 1.0
        else:
            duty = min(mag / chosen.actual_rate, 1.0)

        self._current_class = chosen
        return chosen, duty, sign

    def _select_class(self, mag: float) -> RateClass | None:
        """ヒステリシス付きでクラスを選ぶ。

        現在使用中のクラスがあり、まだそのクラスの実効速度の範囲内
        (境界 +- hysteresis 分だけ広げた範囲)に収まっているなら、
        同じクラスを使い続けて細かい切り替えを防ぐ。
        """
        # 現在のクラスを優先的に維持できるか確認
        if self._current_class is not None:
            idx = self.classes.index(self._current_class)
            lower_bound = (
                self.classes[idx - 1].actual_rate * (1 + self.hysteresis)
                if idx > 0
                else 0.0
            )
            upper_bound = self._current_class.actual_rate * (1 + self.hysteresis)
            if lower_bound <= mag <= upper_bound:
                return self._current_class

        # 通常の選択: magを賄える最小のクラス
        for cls in self.classes:
            if mag <= cls.actual_rate:
                return cls

        return None  # どのクラスの速度でも足りない -> 呼び出し側で頭打ち処理