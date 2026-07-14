"""
ASCOM E-ZEUS II赤道儀制御

ASCOM経由でE-ZEUS IIを制御する実装
"""

import time
import win32com.client
from typing import Optional

from .interface import (
    MountInterface,
    MountCapability,
    GuideDirection,
    MountPosition
)
from utils.units import CoordinateConverter


class ASCOMTelescope(MountInterface):
    """
    ASCOM E-ZEUS Telescope実装
    
    ASCOM Platform経由でE-ZEUS IIを制御する
    """
    
    def __init__(self):
        """初期化"""
        self.scope: Optional[object] = None
        self._capabilities: set[MountCapability] = set()
        self._is_connected = False
    
    def connect(self) -> None:
        """
        ASCOM経由で赤道儀に接続
        
        Raises:
            RuntimeError: 接続失敗時
        """
        try:
            # ASCOM Chooser初期化
            try:
                chooser = win32com.client.Dispatch(
                    "ASCOM.Utilities.Chooser"
                )
            except Exception as e:
                raise RuntimeError(
                    f"ASCOM Utilitiesの初期化に失敗しました: {e}"
                ) from e
            
            # ドライバ選択
            chooser.DeviceType = "Telescope"
            progid = chooser.Choose(None)
            
            if progid is None:
                raise RuntimeError(
                    "望遠鏡ドライバが選択されませんでした"
                )
            
            # ドライバ初期化
            try:
                self.scope = win32com.client.Dispatch(progid)
            except Exception as e:
                self.scope = None
                raise RuntimeError(
                    f"ドライバの初期化に失敗しました ({progid}): {e}"
                ) from e
            
            # 接続確立
            try:
                print(self.scope.DriverInfo)
                print(self.scope.DriverVersion)
                print(self.scope.InterfaceVersion)

                self.scope.Connected = True
            except Exception as e:
                self.scope = None
                raise RuntimeError(
                    f"ドライバへの接続に失敗しました: {e}"
                ) from e
                        
            self._is_connected = True
            
            # 機能確認
            self._detect_capabilities()      

            if self.scope.AtPark:
                print("Unparking...")
                self.scope.Unpark()

            # 恒星追尾をON
            if not self.scope.Tracking:
                print("Tracking ON")
                self.scope.Tracking = True

            try:
                if self.scope.Slewing:
                    print("Abort previous slew")
                    self.scope.AbortSlew()
            except Exception:
                pass

            print(f"✓ 接続成功: {progid}")
            print(f"  機能: {', '.join([c.name for c in self._capabilities])}")

            print("CanPark =", self.scope.CanPark)
            print("CanUnpark =", self.scope.CanUnpark)
            

            print(f"Tracking = {self.scope.Tracking}")
            print(f"AtPark   = {self.scope.AtPark}")
            print(f"Slewing  = {self.scope.Slewing}")
        except Exception:
            self._is_connected = False
            raise
    
    def disconnect(self) -> None:
        """赤道儀から切断"""
        try:
            if self.scope is not None:
                try:
                    self.scope.Connected = False
                except:
                    pass  # 既に切断済みの可能性
            self._is_connected = False
            self.scope = None
            print("✓ 切断完了")
        except Exception as e:
            print(f"⚠ 切断時エラー: {e}")
    
    def is_connected(self) -> bool:
        """接続状態確認"""
        if not self._is_connected or self.scope is None:
            return False
        
        try:
            return bool(self.scope.Connected)
        except:
            return False
    
    def get_position(self) -> MountPosition:
        """
        現在位置取得
        
        Returns:
            MountPosition: (RA時間, Dec度)
            
        Raises:
            RuntimeError: 未接続またはASCOMエラー
        """
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        try:
            ra_hours = float(self.scope.RightAscension)
            dec_degrees = float(self.scope.Declination)
            
            # 値を正規化
            ra_hours = CoordinateConverter.normalize_ra_hours(ra_hours)
            dec_degrees = CoordinateConverter.normalize_dec_degrees(dec_degrees)
            
            return MountPosition(ra_hours, dec_degrees)
            
        except Exception as e:
            raise RuntimeError(f"位置取得エラー: {e}") from e
    
    def slew_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float,
        async_: bool = True
    ) -> None:
        """
        指定座標へGoTO実行
        
        Args:
            ra_hours: 目標赤経 (0-24時間)
            dec_degrees: 目標赤緯 (-90-90度)
            async_: 非同期なら True
            
        Raises:
            RuntimeError: 未接続またはドライバエラー
            ValueError: 不正な座標値
        """
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")

        if MountCapability.CAN_SLEW not in self._capabilities:
            raise RuntimeError("このドライバはSlewをサポートしていません")
        
        # 座標値チェック
        if not (0 <= ra_hours <= 24):
            raise ValueError(f"RA範囲外: {ra_hours}h (0-24で指定)")
        if not (-90 <= dec_degrees <= 90):
            raise ValueError(f"Dec範囲外: {dec_degrees}° (-90-90で指定)")
        
        try:
            if async_:
                self.scope.SlewToCoordinatesAsync(ra_hours, dec_degrees)
                print(
                    f"Slew開始 (非同期): "
                    f"RA={ra_hours:.4f}h, Dec={dec_degrees:.4f}°"
                )
            else:
                self.scope.SlewToCoordinates(ra_hours, dec_degrees)
                print(
                    f"Slew完了 (同期): "
                    f"RA={ra_hours:.4f}h, Dec={dec_degrees:.4f}°"
                )
        except Exception as e:
            raise RuntimeError(f"Slew実行エラー: {e}") from e
    
    def wait_slew(self, timeout_sec: float = 300) -> None:
        """
        進行中のSlew完了待機
        
        Args:
            timeout_sec: タイムアウト時間（秒）
            
        Raises:
            RuntimeError: 未接続
            TimeoutError: タイムアウト
        """
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        start_time = time.time()
        check_interval = 0.2  # 200msごとに確認
        last_print_time = start_time
        
        try:
            while True:
                elapsed = time.time() - start_time
                
                # タイムアウトチェック
                if elapsed > timeout_sec:
                    raise TimeoutError(
                        f"Slew完了タイムアウト ({timeout_sec}秒経過)"
                    )
                
                # Slewing状態確認
                try:
                    is_slewing = self.scope.Slewing
                except Exception as e:
                    raise RuntimeError(f"Slewing状態確認エラー: {e}") from e
                
                if not is_slewing:
                    print(f"✓ Slew完了 ({elapsed:.1f}秒)")
                    break
                
                # 定期的に進行状況表示
                if time.time() - last_print_time > 2.0:
                    print(f"  Slew中... ({elapsed:.1f}秒経過)")
                    last_print_time = time.time()
                
                time.sleep(check_interval)
        
        except Exception:
            raise
    
    def pulse_guide(
        self,
        direction: GuideDirection,
        duration_ms: int
    ) -> None:
        """
        PulseGuide実行
        
        Args:
            direction: ガイド方向
            duration_ms: パルス時間（ミリ秒）
            
        Raises:
            RuntimeError: 未接続またはドライバエラー
            ValueError: duration_msが範囲外
        """
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        if MountCapability.CAN_PULSE_GUIDE not in self._capabilities:
            raise RuntimeError("このドライバはPulseGuideをサポートしていません")
        
        # パラメータチェック
        if not isinstance(direction, GuideDirection):
            raise TypeError(f"direction は GuideDirection 型である必要があります")
        
        if not (0 <= duration_ms <= 30000):
            raise ValueError(
                f"パルス時間は0-30000msの範囲です: {duration_ms}ms"
            )
        
        if duration_ms == 0:
            return  # 0msは実行しない
        
        try:
            self.scope.PulseGuide(direction.value, duration_ms)
            # ※ ここではデバッグ出力は控える（頻繁に呼ばれるため）
        except Exception as e:
            raise RuntimeError(f"PulseGuide実行エラー: {e}") from e
    
    def sync_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float
    ) -> None:
        """
        座標同期（位置合わせ）
        
        Args:
            ra_hours: 同期赤経 (0-24時間)
            dec_degrees: 同期赤緯 (-90-90度)
            
        Raises:
            RuntimeError: 未接続またはドライバエラー
        """
        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")

        if MountCapability.CAN_SYNC not in self._capabilities:
            raise RuntimeError(
                "このドライバはSyncをサポートしていません"
            )

        try:
            # Targetも設定しておく
            try:
                self.scope.TargetRightAscension = ra_hours
                self.scope.TargetDeclination = dec_degrees
            except Exception:
                pass

            try:
                self.scope.SyncToCoordinates(
                    ra_hours,
                    dec_degrees,
                )
            except Exception:
                self.scope.SyncToTarget()

            print(
                f"✓ Sync完了: "
                f"RA={ra_hours:.4f}h "
                f"Dec={dec_degrees:.4f}°"
            )

        except Exception as e:
            raise RuntimeError(
                f"Sync実行エラー: {e}"
            ) from e
    
    def get_capabilities(self) -> set[MountCapability]:
        """利用可能な機能一覧"""
        return self._capabilities.copy()

    def sync_home_position(self, ra_hours: float) -> None:
        """ホームポジションでSyncする"""

        self.sync_to_coordinates(
            ra_hours=ra_hours,
            dec_degrees=90.0,
        )
    
    def _detect_capabilities(self) -> None:
        """利用可能な機能を検出"""
        self._capabilities.clear()
        
        try:
            # PulseGuide対応確認
            if self._safe_getattr(self.scope, 'CanPulseGuide', False):
                self._capabilities.add(MountCapability.CAN_PULSE_GUIDE)
            
            # MoveAxis対応確認
            if self._safe_getattr(self.scope, 'CanMoveAxis', False):
                self._capabilities.add(MountCapability.CAN_MOVE_AXIS)
            
            # Sync対応確認
            if self._safe_getattr(self.scope, 'CanSync', False):
                self._capabilities.add(MountCapability.CAN_SYNC)
            
            # Slew対応確認
            if self._safe_getattr(self.scope, 'CanSlew', False):
                self._capabilities.add(MountCapability.CAN_SLEW)
        
        except Exception as e:
            print(f"⚠ 機能検出エラー: {e}")


    def move_axis(
        self,
        axis: int,
        rate: float,
    ) -> None:

        if not self.is_connected():
            raise RuntimeError("赤道儀が未接続です")

        if MountCapability.CAN_MOVE_AXIS not in self._capabilities:
            raise RuntimeError("MoveAxis非対応")
        
        try:
            self.scope.MoveAxis(axis, rate)
        except Exception as e:
            raise RuntimeError(
                f"MoveAxis実行エラー: {e}"
            ) from e
    
    @staticmethod
    def _safe_getattr(obj, attr_name: str, default=False):
        """
        ASCOM COMオブジェクトの属性を安全に取得
        
        Args:
            obj: COMオブジェクト
            attr_name: 属性名
            default: デフォルト値
            
        Returns:
            属性値、またはデフォルト値
        """
        try:
            value = getattr(obj, attr_name, None)
            return bool(value) if value is not None else default
        except:
            return default
