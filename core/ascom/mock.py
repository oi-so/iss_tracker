"""
赤道儀シミュレータ

テスト・デバッグ用の仮想赤道儀実装
"""

from .interface import (
    MountInterface,
    MountCapability,
    GuideDirection,
    MountPosition
)
from utils.units import CoordinateConverter


class MountSimulator(MountInterface):
    """
    赤道儀シミュレータ
    
    テスト時にASCOM赤道儀の代わりに使用
    """
    
    def __init__(self):
        """初期化"""
        self.ra_hours: float = 0.0
        self.dec_degrees: float = 0.0
        self._is_connected = False
        
        # ガイド状態
        self.guide_ra_rate: float = 0.0   # 度/秒
        self.guide_dec_rate: float = 0.0  # 度/秒
        
        # シミュレーション用
        self.slew_speed = 1.0  # 度/秒
    
    def connect(self) -> None:
        """接続（シミュレータ）"""
        self._is_connected = True
        print("✓ シミュレータ接続")
    
    def disconnect(self) -> None:
        """切断（シミュレータ）"""
        self._is_connected = False
        print("✓ シミュレータ切断")
    
    def is_connected(self) -> bool:
        """接続状態"""
        return self._is_connected
    
    def get_position(self) -> MountPosition:
        """現在位置取得"""
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        return MountPosition(self.ra_hours, self.dec_degrees)
    
    def slew_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float,
        async_: bool = True
    ) -> None:
        """GoTO実行"""
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        if not (0 <= ra_hours <= 24):
            raise ValueError(f"RA範囲外: {ra_hours}h")
        if not (-90 <= dec_degrees <= 90):
            raise ValueError(f"Dec範囲外: {dec_degrees}°")
        
        self.ra_hours = CoordinateConverter.normalize_ra_hours(ra_hours)
        self.dec_degrees = CoordinateConverter.normalize_dec_degrees(dec_degrees)
        
        ra_deg = CoordinateConverter.ra_hours_to_degrees(self.ra_hours)
        
        print(
            f"Slew {'非同期' if async_ else '同期'}: "
            f"RA={self.ra_hours:.4f}h ({ra_deg:.2f}°), "
            f"Dec={self.dec_degrees:.4f}°"
        )
    
    def wait_slew(self, timeout_sec: float = 300) -> None:
        """Slew完了待機"""
        print(f"✓ Slew完了 (シミュレータ)")
    
    def pulse_guide(
        self,
        direction: GuideDirection,
        duration_ms: int
    ) -> None:
        """PulseGuide実行"""
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        if not (0 <= duration_ms <= 30000):
            raise ValueError(f"パルス時間は0-30000ms: {duration_ms}")
        
        if duration_ms == 0:
            return
        
        # ガイド速度を計算（仮定: 速度 = 補正量 / 継続時間）
        guide_speed = 0.1  # 度/100ms（仮定値）
        correction = guide_speed * (duration_ms / 100.0)
        
        if direction == GuideDirection.NORTH:
            self.dec_degrees += correction
        elif direction == GuideDirection.SOUTH:
            self.dec_degrees -= correction
        elif direction == GuideDirection.EAST:
            self.ra_hours += CoordinateConverter.ra_degrees_to_hours(correction)
        elif direction == GuideDirection.WEST:
            self.ra_hours -= CoordinateConverter.ra_degrees_to_hours(correction)
        
        # 正規化
        self.ra_hours = CoordinateConverter.normalize_ra_hours(self.ra_hours)
        self.dec_degrees = CoordinateConverter.normalize_dec_degrees(self.dec_degrees)
        
        # ※ デバッグ出力は削減（頻繁に呼ばれるため）
    
    def sync_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float
    ) -> None:
        """座標同期"""
        self.ra_hours = CoordinateConverter.normalize_ra_hours(ra_hours)
        self.dec_degrees = CoordinateConverter.normalize_dec_degrees(dec_degrees)
        
        ra_deg = CoordinateConverter.ra_hours_to_degrees(self.ra_hours)
        print(f"✓ Sync: RA={self.ra_hours:.4f}h ({ra_deg:.2f}°), Dec={self.dec_degrees:.4f}°")
    
    def get_capabilities(self) -> set[MountCapability]:
        """利用可能な機能"""
        return {
            MountCapability.CAN_PULSE_GUIDE,
            MountCapability.CAN_SLEW,
            MountCapability.CAN_SYNC,
        }
    
    def update(self, dt: float) -> None:
        """
        シミュレーション更新
        
        ガイド速度に基づいて位置を更新
        
        Args:
            dt: 時間経過（秒）
        """
        # RA更新
        if self.guide_ra_rate != 0:
            delta_deg = self.guide_ra_rate * dt
            delta_h = CoordinateConverter.ra_degrees_to_hours(delta_deg)
            self.ra_hours += delta_h
            self.ra_hours = CoordinateConverter.normalize_ra_hours(self.ra_hours)
        
        # Dec更新
        if self.guide_dec_rate != 0:
            delta_deg = self.guide_dec_rate * dt
            self.dec_degrees += delta_deg
            self.dec_degrees = CoordinateConverter.normalize_dec_degrees(self.dec_degrees)
