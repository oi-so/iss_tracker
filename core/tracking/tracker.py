"""
ISS追尾制御メインループ

ISS軌道計算と赤道儀制御を統合
"""

import time
from datetime import datetime

from core.ascom.interface import MountInterface
from core.astronomy.orbit_calculator import OrbitCalculator
from core.tracking.guider import Guider
from utils.units import CoordinateConverter


class TrackingConfig:
    """追尾設定"""
    pulse_interval_sec: float = 0.05  # パルス間隔（秒）
    max_slew_time_sec: float = 60.0   # Slew最大時間（秒）
    slew_padding_sec: float = 5.0     # Slew時間の安全マージン（秒）


class ISSTracker:
    """
    ISS追尾コントローラー
    
    ISS軌道計算、赤道儀操作、ガイド制御を統合
    """
    
    def __init__(
        self,
        mount: MountInterface,
        orbit: OrbitCalculator,
        guider: Guider = None,
        config: TrackingConfig = None
    ):
        """
        初期化
        
        Args:
            mount: 赤道儀
            orbit: ISS軌道計算
            guider: ガイダー（Noneなら自動生成）
            config: 追尾設定
        """
        self.mount = mount
        self.orbit = orbit
        self.guider = guider or Guider(mount)
        self.config = config or TrackingConfig()
        self.offset_sec = 0.0  # 追尾開始時刻のオフセット（秒）
        
        self.is_tracking = False
    
    def acquire(self, target_time: datetime) -> None:
        """
        ISS自動導入（acquire）
        
        現在位置からISS未来位置へGoTo実行
        
        Args:
            target_time: 目標時刻（UTC）
            
        Raises:
            RuntimeError: 未接続またはドライバエラー
        """
        if not self.mount.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        # 現在位置確認
        current_pos = self.mount.get_position()
        print(
            f"現在位置: RA={current_pos.ra_hours:.4f}h, "
            f"Dec={current_pos.dec_degrees:.4f}°"
        )
        
        # 現在位置（度）
        current_ra_deg = CoordinateConverter.ra_hours_to_degrees(
            current_pos.ra_hours
        )
        current_dec_deg = current_pos.dec_degrees
        
        # ISS現在位置取得
        skyfield_time = self.orbit.ts.from_datetime(target_time)
        current_iss_pos = self.orbit.get_position_at(skyfield_time)
        
        target_ra_deg = CoordinateConverter.ra_hours_to_degrees(
            current_iss_pos.ra.hours
        )
        target_dec_deg = current_iss_pos.dec.degrees
        
        # Slew時間推定
        slew_time = self._estimate_slew_time(
            current_ra_deg,
            current_dec_deg,
            target_ra_deg,
            target_dec_deg
        )
        
        print(f"推定Slew時間: {slew_time:.1f}秒")
        
        # ISS未来位置を計算（Slew時間を考慮）
        future_iss_pos = self.orbit.get_position_after(
            skyfield_time,
            slew_time + self.offset_sec
        )
        
        target_ra_hours = future_iss_pos.ra.hours
        target_dec_degrees = future_iss_pos.dec.degrees
        
        target_ra_deg = CoordinateConverter.ra_hours_to_degrees(target_ra_hours)
        
        print(
            f"目標位置 (Slew考慮): "
            f"RA={target_ra_hours:.4f}h ({target_ra_deg:.2f}°), "
            f"Dec={target_dec_degrees:.4f}°"
        )
        
        # GoTo実行
        self.mount.slew_to_coordinates(
            target_ra_hours,
            target_dec_degrees,
            async_=True
        )
        
        # 完了待機
        try:
            self.mount.wait_slew(
                timeout_sec=slew_time + self.config.slew_padding_sec
            )
        except Exception as e:
            print(f"⚠ GoTO警告: {e}")
    
    def start_tracking(
        self,
        start_time: datetime,
        duration_sec: float
    ) -> None:
        """
        ISS追尾開始
        
        Args:
            start_time: 追尾開始時刻（UTC）
            duration_sec: 追尾継続時間（秒）
        """
        if not self.mount.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        self.is_tracking = True
        
        skyfield_time = self.orbit.ts.from_datetime(start_time)
        start_perf = time.perf_counter()
        next_pulse = start_perf
        
        print(f"追尾開始 (継続時間: {duration_sec:.0f}秒)")
        
        try:
            iteration = 0
            
            while self.is_tracking:
                elapsed = time.perf_counter() - start_perf
                
                # 終了チェック
                if elapsed > duration_sec:
                    print(f"追尾終了 (目標時間経過)")
                    break
                
                # ISS現在位置取得
                current_iss_pos = self.orbit.get_position_after(
                    skyfield_time,
                    elapsed + self.offset_sec
                )
                
                # ISS未来位置取得（速度計算用）
                future_iss_pos = self.orbit.get_position_after(
                    skyfield_time,
                    elapsed + self.config.pulse_interval_sec + self.offset_sec
                )
                
                # ISS位置（度）
                iss_ra_deg = CoordinateConverter.ra_hours_to_degrees(
                    current_iss_pos.ra.hours
                )
                iss_dec_deg = current_iss_pos.dec.degrees
                
                # ISS速度計算
                future_ra_deg = CoordinateConverter.ra_hours_to_degrees(
                    future_iss_pos.ra.hours
                )
                future_dec_deg = future_iss_pos.dec.degrees
                
                ra_velocity_deg_per_sec = (
                    (self._shortest_angle_diff_deg(iss_ra_deg, future_ra_deg)) /
                    self.config.pulse_interval_sec
                )
                dec_velocity_deg_per_sec = (
                    (future_dec_deg - iss_dec_deg) /
                    self.config.pulse_interval_sec
                )
                
                # 赤道儀現在位置取得
                mount_pos = self.mount.get_position()
                mount_ra_deg = CoordinateConverter.ra_hours_to_degrees(
                    mount_pos.ra_hours
                )
                mount_dec_deg = mount_pos.dec_degrees
                
                # 位置誤差計算
                ra_error_deg = self._shortest_angle_diff_deg(mount_ra_deg, iss_ra_deg)
                dec_error_deg = iss_dec_deg - mount_dec_deg
                
                # ガイド補正実行
                self.guider.guide(
                    ra_velocity_deg_per_sec,
                    dec_velocity_deg_per_sec,
                    ra_error_deg,
                    dec_error_deg
                )
                
                # ロギング（10回に1回）
                if iteration % 10 == 0:
                    print(
                        f"T={elapsed:6.2f}s | "
                        f"ISS: {iss_ra_deg:6.2f}°/{iss_dec_deg:6.2f}° | "
                        f"Mount: {mount_ra_deg:6.2f}°/{mount_dec_deg:6.2f}° | "
                        f"Err: {ra_error_deg:6.2f}°/{dec_error_deg:6.2f}°"
                    )
                
                # 次のパルスまで待機
                sleep_time = next_pulse - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                
                next_pulse += self.config.pulse_interval_sec
                iteration += 1
        
        except KeyboardInterrupt:
            print("追尾中止 (ユーザー入力)")
        except Exception as e:
            print(f"追尾エラー: {e}")
            self.is_tracking = False
            raise
    
    def stop_tracking(self) -> None:
        """追尾停止"""
        self.is_tracking = False
        print("追尾停止要求")
    
    def _estimate_slew_time(
        self,
        from_ra_deg: float,
        from_dec_deg: float,
        to_ra_deg: float,
        to_dec_deg: float
    ) -> float:
        """
        Slew時間推定
        
        現在位置から目標位置までの角度差から推定
        
        Args:
            from_ra_deg: 現在RA（度）
            from_dec_deg: 現在Dec（度）
            to_ra_deg: 目標RA（度）
            to_dec_deg: 目標Dec（度）
            
        Returns:
            float: 推定Slew時間（秒）
        """
        # 角度差計算（大円距離）
        delta_ra = abs(to_ra_deg - from_ra_deg)
        
        # 360度を超える場合は逆方向が短い
        if delta_ra > 180:
            delta_ra = 360 - delta_ra
        
        delta_dec = abs(to_dec_deg - from_dec_deg)
        
        # 最大角度差
        max_delta = max(delta_ra, delta_dec)
        
        # 仮定: 赤道儀は1度/秒で移動
        estimated = max_delta / 1.0
        
        # 上限を設定
        estimated = min(estimated, self.config.max_slew_time_sec)
        
        return estimated

    @staticmethod
    def _shortest_angle_diff_deg(from_deg: float, to_deg: float) -> float:
        """角度差 (to - from) を -180..180 の範囲で返す。"""
        diff = (to_deg - from_deg + 180.0) % 360.0 - 180.0
        return diff



    def set_offset(self, offset_sec: float) -> None:
        self.offset_sec = offset_sec

    def get_offset(self) -> float:
        return self.offset_sec
    
    def adjust_offset(self, delta_sec: float) -> None:
        """追尾時刻オフセットを増減する"""
        self.offset_sec += delta_sec
        print(f"\nTime Offset = {self.offset_sec:+.2f} s")
