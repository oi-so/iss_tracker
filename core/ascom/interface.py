"""
ASCOM赤道儀制御の抽象インターフェース

このモジュールは、異なる赤道儀実装を統一的に扱うための
インターフェース定義を提供します。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class MountCapability(Enum):
    """赤道儀の利用可能な機能"""
    CAN_PULSE_GUIDE = 1      # PulseGuide対応
    CAN_MOVE_AXIS = 2         # MoveAxis対応
    CAN_SYNC = 4              # Sync対応
    CAN_SLEW = 8              # Slew対応


class GuideDirection(Enum):
    """
    ASCOM PulseGuide方向定義
    
    ASCOMドライバが期待する方向コード
    """
    NORTH = 0  # 北
    SOUTH = 1  # 南
    EAST = 2   # 東
    WEST = 3   # 西


@dataclass
class MountPosition:
    """赤道儀の位置（赤経・赤緯）"""
    ra_hours: float        # 赤経 (0-24時間)
    dec_degrees: float     # 赤緯 (-90 - +90度)


class MountInterface(ABC):
    """
    赤道儀の抽象インターフェース
    
    ASCOM経由の実装、シミュレータなど、
    異なる赤道儀実装を統一的に扱うための基底クラス
    """
    
    @abstractmethod
    def connect(self) -> None:
        """
        赤道儀に接続
        
        Raises:
            RuntimeError: 接続失敗時
        """
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """
        赤道儀から切断
        
        既に切断済みでもエラーにしない
        """
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """
        接続状態確認
        
        Returns:
            bool: 接続中ならTrue
        """
        pass
    
    @abstractmethod
    def get_position(self) -> MountPosition:
        """
        現在位置取得
        
        赤道儀が現在向いている座標（赤経・赤緯）を取得
        
        Returns:
            MountPosition: 現在位置
            
        Raises:
            RuntimeError: 未接続、またはASCOMエラー
        """
        pass
    
    @abstractmethod
    def slew_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float,
        async_: bool = True
    ) -> None:
        """
        指定座標へGoTo実行
        
        Args:
            ra_hours: 目標赤経 (0-24時間)
            dec_degrees: 目標赤緯 (-90 - +90度)
            async_: Trueなら非同期実行、Falseなら完了まで待機
            
        Raises:
            RuntimeError: 未接続、またはドライバエラー
            ValueError: 不正な座標値
        """
        pass
    
    @abstractmethod
    def wait_slew(self, timeout_sec: float = 300) -> None:
        """
        進行中のGoTo完了待機
        
        slew_to_coordinates(async_=True)実行後、
        完了するまで待機する。
        
        Args:
            timeout_sec: タイムアウト時間（秒）
            
        Raises:
            RuntimeError: 未接続
            TimeoutError: タイムアウト
        """
        pass
    
    @abstractmethod
    def pulse_guide(
        self,
        direction: GuideDirection,
        duration_ms: int
    ) -> None:
        """
        PulseGuide実行(使用非推奨)
        
        微小な補正移動を実行。推尾制御で使用。
        
        Args:
            direction: ガイド方向（ASCOM GuideDirection）
            duration_ms: パルス時間（ミリ秒）、0-30000
            
        Raises:
            RuntimeError: 未接続、またはドライバエラー
            ValueError: duration_msが範囲外
        """
        pass
    
    @abstractmethod
    def sync_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float
    ) -> None:
        """
        座標同期（位置合わせ）
        
        赤道儀の現在位置を指定座標に合わせる。
        モーター角度と座標の対応付けを修正。
        
        Args:
            ra_hours: 同期赤経 (0-24時間)
            dec_degrees: 同期赤緯 (-90 - +90度)
            
        Raises:
            RuntimeError: 未接続、またはドライバエラー
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> set[MountCapability]:
        """
        利用可能な機能一覧取得
        
        Returns:
            set[MountCapability]: サポートされている機能
        """
        pass



    # @abstractmethod
    def move_axis(
        self,
        axis: int,
        rate: float,
    ) -> None:
        """
        軸を一定速度で回転させる

        axis(0=RA,1=DEC)方向に、rate(度/秒)で回転させる。

        Args:
            axis: 0=RA, 1=DEC
            rate: 回転速度（度/秒）、正負で方向指定
        """
