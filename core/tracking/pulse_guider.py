from core.ascom.interface import MountInterface, GuideDirection
from .guider import Guider


class PulseGuiderConfig:
    """ガイダー設定"""
    kp: float = 0.05  # P制御ゲイン
    max_pulse_ms: int = 500  # 最大パルス時間
    dead_band_deg: float = 0.01  # デッドバンド（度）
    pulse_gain_ms_per_deg_per_sec: float = 1000.0  # 速度→パルス時間 変換ゲイン


class PulseGuider(Guider):
    def __init__(
        self,
        mount: MountInterface,
        config: PulseGuiderConfig = None
    ):
        """
        初期化
        
        Args:
            mount: 赤道儀インターフェース
            config: ガイダー設定
        """
        super().__init__(mount, config or PulseGuiderConfig())
    
    def guide(
        self,
        ra_velocity_deg_per_sec: float,
        dec_velocity_deg_per_sec: float,
        ra_error_deg: float,
        dec_error_deg: float
    ) -> None:
        """
        ガイド補正実行
        
        ISS速度（予測追尾）と位置誤差（P制御）を合わせて
        PulseGuideを生成・実行
        
        Args:
            ra_velocity_deg_per_sec: ISS RA速度（度/秒）
            dec_velocity_deg_per_sec: ISS Dec速度（度/秒）
            ra_error_deg: RA位置誤差（度）
            dec_error_deg: Dec位置誤差（度）
        """
        # RA方向の補正速度計算
        # = 予測追尾速度 + P制御補正
        ra_rate_deg_per_sec = (
            ra_velocity_deg_per_sec +
            ra_error_deg * self.config.kp
        )
        
        # Dec方向の補正速度計算
        dec_rate_deg_per_sec = (
            dec_velocity_deg_per_sec +
            dec_error_deg * self.config.kp
        )
        
        # PulseGuide実行
        self._execute_pulse_guide(
            ra_rate_deg_per_sec,
            dec_rate_deg_per_sec
        )
    
    def _execute_pulse_guide(
        self,
        ra_rate_deg_per_sec: float,
        dec_rate_deg_per_sec: float
    ) -> None:
        """
        PulseGuide実行
        
        速度（度/秒）をパルス時間（ミリ秒）に変換して実行
        
        Args:
            ra_rate_deg_per_sec: RA補正速度（度/秒）
            dec_rate_deg_per_sec: Dec補正速度（度/秒）
        """
        # RA補正
        if abs(ra_rate_deg_per_sec) > self.config.dead_band_deg:
            ra_direction = (
                GuideDirection.EAST
                if ra_rate_deg_per_sec > 0
                else GuideDirection.WEST
            )
            
            # 速度 → パルス時間に変換
            ra_pulse_ms = int(
                abs(ra_rate_deg_per_sec) * self.config.pulse_gain_ms_per_deg_per_sec
            )
            ra_pulse_ms = min(self.config.max_pulse_ms, ra_pulse_ms)
            
            if ra_pulse_ms > 0:
                try:
                    self.mount.pulse_guide(ra_direction, ra_pulse_ms)
                except Exception as e:
                    print(f"RA PulseGuideエラー: {e}")
        
        # Dec補正
        if abs(dec_rate_deg_per_sec) > self.config.dead_band_deg:
            dec_direction = (
                GuideDirection.NORTH
                if dec_rate_deg_per_sec > 0
                else GuideDirection.SOUTH
            )
            
            # 速度 → パルス時間に変換
            dec_pulse_ms = int(
                abs(dec_rate_deg_per_sec) * self.config.pulse_gain_ms_per_deg_per_sec
            )
            dec_pulse_ms = min(self.config.max_pulse_ms, dec_pulse_ms)
            
            if dec_pulse_ms > 0:
                try:
                    self.mount.pulse_guide(dec_direction, dec_pulse_ms)
                except Exception as e:
                    print(f"Dec PulseGuideエラー: {e}")

    def stop(self) -> None:
        pass
