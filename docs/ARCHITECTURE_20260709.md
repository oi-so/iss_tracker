# ISS追尾システム - 改善アーキテクチャ設計

**バージョン**: 1.0  
**作成日**: 2026-07-09

---

## 📐 推奨する新しいアーキテクチャ

### 現在の構成 vs 推奨構成

#### 現在
```
config.py
models.py
tle.py          → orbit.py → predictor.py
telescope.py    → tracker.py → guider.py → main.py
telescope_simulator.py
```

#### 推奨
```
config/
├── settings.py (観測地点、パラメータ)
├── constants.py (単位変換、ASCOM定数)

core/
├── ascom/
│   ├── interface.py (抽象基底)
│   ├── telescope.py (ASCOM実装)
│   └── mock.py (テスト用Simulator)
├── astronomy/
│   ├── tle_loader.py
│   ├── orbit_calculator.py
│   ├── coordinate_transform.py
│   └── time_sync.py
├── tracking/
│   ├── tracker.py
│   ├── guider.py (P/PID制御)
│   └── safety.py (衝突検出など)

models/
├── position.py (Position, Velocity)
├── error.py (カスタム例外)

utils/
├── units.py (単位変換)
└── logger.py (ロギング)

tests/
├── test_ascom_*.py
├── test_astronomy_*.py
├── test_tracking_*.py

main.py
```

---

## 🏗️ 詳細設計

### 1. 抽象インターフェース層

#### `core/ascom/interface.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

class MountCapability(Enum):
    """赤道儀の機能フラグ"""
    CAN_PULSE_GUIDE = 1
    CAN_MOVE_AXIS = 2
    CAN_SYNC = 4
    CAN_SLEW = 8

class GuideDirection(Enum):
    """ASCOM ガイド方向"""
    NORTH = 0
    SOUTH = 1
    EAST = 2
    WEST = 3

@dataclass
class MountState:
    """赤道儀の状態"""
    ra_hours: float  # 0-24
    dec_degrees: float  # -90-90
    is_slewing: bool
    capabilities: set[MountCapability]

class MountInterface(ABC):
    """赤道儀の抽象インターフェース"""
    
    @abstractmethod
    def connect(self) -> None:
        """接続"""
        pass
    
    @abstractmethod
    def disconnect(self) -> None:
        """切断"""
        pass
    
    @abstractmethod
    def is_connected(self) -> bool:
        """接続状態確認"""
        pass
    
    @abstractmethod
    def get_position(self) -> tuple[float, float]:
        """
        現在位置取得
        
        Returns:
            (ra_hours, dec_degrees)
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
        GoTo実行
        
        Args:
            ra_hours: 赤経 (0-24)
            dec_degrees: 赤緯 (-90-90)
            async_: 非同期実行
        """
        pass
    
    @abstractmethod
    def wait_slew(self, timeout_sec: float = 300) -> None:
        """GoTo完了待機"""
        pass
    
    @abstractmethod
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
        """
        pass
    
    @abstractmethod
    def sync_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float
    ) -> None:
        """座標同期"""
        pass
    
    @abstractmethod
    def get_capabilities(self) -> set[MountCapability]:
        """利用可能な機能一覧"""
        pass
```

---

### 2. 座標系・単位管理

#### `config/constants.py`

```python
# 単位変換定数
HOURS_TO_DEGREES = 15.0  # 1時間 = 15度
DEGREES_TO_HOURS = 1.0 / HOURS_TO_DEGREES

# 座標系
class CoordinateSystem:
    """座標系定義"""
    J2000 = "J2000"          # 赤道座標 (標準)
    TOPOCENTRIC = "TOPOCENTRIC"  # 視座標

# ASCOM方向定数
ASCOM_GUIDE_DIRECTIONS = {
    "north": 0,
    "south": 1,
    "east": 2,
    "west": 3,
}
```

#### `utils/units.py`

```python
class CoordinateConverter:
    """座標系・単位変換"""
    
    @staticmethod
    def ra_hours_to_degrees(ra_hours: float) -> float:
        """赤経: 時間 → 度"""
        return ra_hours * 15.0
    
    @staticmethod
    def ra_degrees_to_hours(ra_degrees: float) -> float:
        """赤経: 度 → 時間"""
        return ra_degrees / 15.0
    
    @staticmethod
    def normalize_ra_hours(ra_hours: float) -> float:
        """赤経を0-24の範囲に正規化"""
        return ra_hours % 24.0
    
    @staticmethod
    def normalize_dec_degrees(dec_degrees: float) -> float:
        """赤緯を-90-90の範囲に正規化"""
        if dec_degrees > 90:
            return 90.0
        if dec_degrees < -90:
            return -90.0
        return dec_degrees
```

---

### 3. ASCOM実装

#### `core/ascom/telescope.py`

```python
import win32com.client
import time
from typing import Optional
from .interface import MountInterface, MountCapability, GuideDirection, MountState

class ASCOMTelescope(MountInterface):
    """ASCOM E-ZEUS制御"""
    
    def __init__(self):
        self.scope: Optional[object] = None
        self._capabilities: set[MountCapability] = set()
    
    def connect(self) -> None:
        """ASCOM経由で赤道儀に接続"""
        try:
            chooser = win32com.client.Dispatch(
                "ASCOM.Utilities.Chooser"
            )
            chooser.DeviceType = "Telescope"
            progid = chooser.Choose(None)
            
            if progid is None:
                raise RuntimeError("望遠鏡ドライバが選択されませんでした")
            
            self.scope = win32com.client.Dispatch(progid)
            self.scope.Connected = True
            
            # 機能確認
            self._detect_capabilities()
            
            print(f"接続完了: {progid}")
            
        except Exception as e:
            self.scope = None
            raise RuntimeError(f"接続失敗: {e}") from e
    
    def disconnect(self) -> None:
        """切断"""
        try:
            if self.scope is not None and self.is_connected():
                self.scope.Connected = False
            self.scope = None
            print("切断完了")
        except Exception as e:
            print(f"切断エラー: {e}")
    
    def is_connected(self) -> bool:
        """接続状態確認"""
        try:
            return self.scope is not None and self.scope.Connected
        except:
            return False
    
    def _detect_capabilities(self) -> None:
        """利用可能な機能を検出"""
        self._capabilities.clear()
        
        try:
            if getattr(self.scope, 'CanPulseGuide', False):
                self._capabilities.add(MountCapability.CAN_PULSE_GUIDE)
            if getattr(self.scope, 'CanMoveAxis', False):
                self._capabilities.add(MountCapability.CAN_MOVE_AXIS)
            if getattr(self.scope, 'CanSync', False):
                self._capabilities.add(MountCapability.CAN_SYNC)
            if getattr(self.scope, 'CanSlew', False):
                self._capabilities.add(MountCapability.CAN_SLEW)
        except Exception as e:
            print(f"機能検出エラー: {e}")
    
    def get_position(self) -> tuple[float, float]:
        """現在位置取得"""
        if not self.is_connected():
            raise RuntimeError("未接続")
        
        try:
            ra_hours = float(self.scope.RightAscension)
            dec_degrees = float(self.scope.Declination)
            return (ra_hours, dec_degrees)
        except Exception as e:
            raise RuntimeError(f"位置取得エラー: {e}") from e
    
    def slew_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float,
        async_: bool = True
    ) -> None:
        """GoTo実行"""
        if not self.is_connected():
            raise RuntimeError("未接続")
        
        if MountCapability.CAN_SLEW not in self._capabilities:
            raise RuntimeError("Slewをサポートしていないドライバです")
        
        try:
            if async_:
                self.scope.SlewToCoordinatesAsync(ra_hours, dec_degrees)
            else:
                self.scope.SlewToCoordinates(ra_hours, dec_degrees)
            print(f"Slew開始: RA={ra_hours:.4f}h, Dec={dec_degrees:.4f}°")
        except Exception as e:
            raise RuntimeError(f"Slew失敗: {e}") from e
    
    def wait_slew(self, timeout_sec: float = 300) -> None:
        """GoTo完了待機"""
        if not self.is_connected():
            raise RuntimeError("未接続")
        
        start_time = time.time()
        check_interval = 0.1
        
        try:
            while True:
                if time.time() - start_time > timeout_sec:
                    raise TimeoutError(f"Slew タイムアウト ({timeout_sec}秒)")
                
                if not self.scope.Slewing:
                    print("Slew完了")
                    break
                
                time.sleep(check_interval)
        except Exception as e:
            raise RuntimeError(f"Slew待機エラー: {e}") from e
    
    def pulse_guide(
        self,
        direction: GuideDirection,
        duration_ms: int
    ) -> None:
        """PulseGuide実行"""
        if not self.is_connected():
            raise RuntimeError("未接続")
        
        if MountCapability.CAN_PULSE_GUIDE not in self._capabilities:
            raise RuntimeError("PulseGuideをサポートしていません")
        
        if duration_ms < 0 or duration_ms > 30000:
            raise ValueError(f"パルス時間は0-30000msの範囲です: {duration_ms}")
        
        try:
            self.scope.PulseGuide(direction.value, duration_ms)
        except Exception as e:
            raise RuntimeError(f"PulseGuide失敗: {e}") from e
    
    def sync_to_coordinates(
        self,
        ra_hours: float,
        dec_degrees: float
    ) -> None:
        """座標同期"""
        if not self.is_connected():
            raise RuntimeError("未接続")
        
        if MountCapability.CAN_SYNC not in self._capabilities:
            raise RuntimeError("Syncをサポートしていません")
        
        try:
            self.scope.SyncToCoordinates(ra_hours, dec_degrees)
            print(f"Sync実行: RA={ra_hours:.4f}h, Dec={dec_degrees:.4f}°")
        except Exception as e:
            raise RuntimeError(f"Sync失敗: {e}") from e
    
    def get_capabilities(self) -> set[MountCapability]:
        """利用可能な機能"""
        return self._capabilities.copy()
```

---

### 4. 追尾制御の改善

#### `core/tracking/tracker.py`

```python
import time
from datetime import datetime
from typing import Callable
from core.ascom.interface import MountInterface, GuideDirection
from core.astronomy.orbit_calculator import OrbitCalculator
from models.position import Velocity
from config.constants import HOURS_TO_DEGREES

class TrackingConfig:
    """追尾設定"""
    max_slew_time: float = 30.0  # 最大Slew時間（秒）
    pulse_interval: float = 0.05  # パルス間隔（秒）
    max_pulse_ms: int = 500  # 最大パルス時間（ミリ秒）
    kp: float = 0.05  # P制御ゲイン

class ISSTracker:
    """ISS追尾コントローラー"""
    
    def __init__(
        self,
        mount: MountInterface,
        orbit: OrbitCalculator,
        config: TrackingConfig = None
    ):
        self.mount = mount
        self.orbit = orbit
        self.config = config or TrackingConfig()
        self.is_tracking = False
    
    def acquire(self, target_time: datetime) -> None:
        """
        ISS導入処理
        
        Args:
            target_time: ISS導入対象時刻
        """
        if not self.mount.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        # 現在位置確認
        current_ra, current_dec = self.mount.get_position()
        print(f"現在位置: RA={current_ra:.4f}h, Dec={current_dec:.4f}°")
        
        # GoToに必要な時間推定
        skyfield_time = self.orbit.ts.from_datetime(target_time)
        
        # 実際のSlew時間を推定
        slew_time = self._estimate_slew_time(
            current_ra, current_dec,
            target_time
        )
        
        # ISS位置を計算（Slew時間を考慮）
        target_position = self.orbit.get_position_after(
            skyfield_time,
            slew_time
        )
        
        target_ra_hours = target_position.ra.hours
        target_dec_degrees = target_position.dec.degrees
        
        print(f"目標位置: RA={target_ra_hours:.4f}h, Dec={target_dec_degrees:.4f}°")
        print(f"推定Slew時間: {slew_time:.1f}秒")
        
        # GoTo実行
        self.mount.slew_to_coordinates(
            target_ra_hours,
            target_dec_degrees,
            async_=True
        )
        
        # 完了待機
        try:
            self.mount.wait_slew(timeout_sec=slew_time + 10)
        except TimeoutError as e:
            print(f"警告: {e}")
    
    def start_tracking(
        self,
        start_time: datetime,
        duration_sec: float
    ) -> None:
        """
        ISS追尾開始
        
        Args:
            start_time: 追尾開始時刻
            duration_sec: 追尾継続時間（秒）
        """
        if not self.mount.is_connected():
            raise RuntimeError("赤道儀が未接続です")
        
        self.is_tracking = True
        
        skyfield_time = self.orbit.ts.from_datetime(start_time)
        start_perf = time.perf_counter()
        next_pulse = start_perf
        
        try:
            while self.is_tracking:
                elapsed = time.perf_counter() - start_perf
                
                if elapsed > duration_sec:
                    print("追尾終了")
                    break
                
                # ISS位置計算
                current_pos = self.orbit.get_position_after(
                    skyfield_time, elapsed
                )
                future_pos = self.orbit.get_position_after(
                    skyfield_time, elapsed + self.config.pulse_interval
                )
                
                # 現在の赤道儀位置
                mount_ra, mount_dec = self.mount.get_position()
                
                # 誤差計算
                iss_ra = current_pos.ra.hours * HOURS_TO_DEGREES
                iss_dec = current_pos.dec.degrees
                
                ra_error = iss_ra - (mount_ra * HOURS_TO_DEGREES)
                dec_error = iss_dec - mount_dec
                
                # 速度計算（予測追尾）
                future_ra = future_pos.ra.hours * HOURS_TO_DEGREES
                future_dec = future_pos.dec.degrees
                
                ra_velocity = (future_ra - iss_ra) / self.config.pulse_interval
                dec_velocity = (future_dec - iss_dec) / self.config.pulse_interval
                
                # P制御で補正速度追加
                ra_rate = ra_velocity + ra_error * self.config.kp
                dec_rate = dec_velocity + dec_error * self.config.kp
                
                # PulseGuide実行
                self._execute_pulse_guide(ra_rate, dec_rate)
                
                # ロギング
                print(
                    f"elapsed={elapsed:.2f}s | "
                    f"ISS: {iss_ra:.2f}°/{iss_dec:.2f}° | "
                    f"Mount: {mount_ra * HOURS_TO_DEGREES:.2f}°/{mount_dec:.2f}° | "
                    f"Error: {ra_error:.2f}°/{dec_error:.2f}°"
                )
                
                # 次のパルスまで待機
                sleep_time = next_pulse - time.perf_counter()
                if sleep_time > 0:
                    time.sleep(sleep_time)
                next_pulse += self.config.pulse_interval
        
        except KeyboardInterrupt:
            print("ユーザー中断")
        except Exception as e:
            print(f"追尾エラー: {e}")
            self.is_tracking = False
            raise
    
    def stop_tracking(self) -> None:
        """追尾停止"""
        self.is_tracking = False
    
    def _estimate_slew_time(
        self,
        from_ra: float,
        from_dec: float,
        to_time: datetime
    ) -> float:
        """Slew時間推定"""
        # 簡易版: 目標位置を取得して角度差から推定
        skyfield_time = self.orbit.ts.from_datetime(to_time)
        target_pos = self.orbit.get_position_at(skyfield_time)
        
        target_ra = target_pos.ra.hours * HOURS_TO_DEGREES
        target_dec = target_pos.dec.degrees
        
        # 角度差計算
        delta_ra = abs(target_ra - from_ra * HOURS_TO_DEGREES)
        delta_dec = abs(target_dec - from_dec)
        
        max_delta = max(delta_ra, delta_dec)
        
        # 仮定: 赤道儀は1°/秒で移動
        estimated_slew = max_delta / 1.0  # °/s = 1.0
        
        return min(estimated_slew, self.config.max_slew_time)
    
    def _execute_pulse_guide(self, ra_rate: float, dec_rate: float) -> None:
        """PulseGuide実行"""
        from core.ascom.interface import GuideDirection
        
        # RA方向
        if abs(ra_rate) > 0.01:  # デッドバンド
            ra_dir = GuideDirection.EAST if ra_rate > 0 else GuideDirection.WEST
            ra_ms = int(abs(ra_rate) * 100) % self.config.max_pulse_ms
            if ra_ms > 0:
                self.mount.pulse_guide(ra_dir, ra_ms)
        
        # Dec方向
        if abs(dec_rate) > 0.01:  # デッドバンド
            dec_dir = GuideDirection.NORTH if dec_rate > 0 else GuideDirection.SOUTH
            dec_ms = int(abs(dec_rate) * 100) % self.config.max_pulse_ms
            if dec_ms > 0:
                self.mount.pulse_guide(dec_dir, dec_ms)
```

---

### 5. 時刻管理の改善

#### `core/astronomy/time_sync.py`

```python
from datetime import datetime, timezone
import time

class TimeSync:
    """システム時刻の同期管理"""
    
    @staticmethod
    def get_utc_now() -> datetime:
        """現在UTC時刻を取得"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def elapsed_seconds(start: datetime) -> float:
        """UTC時刻から経過秒数を計算"""
        now = TimeSync.get_utc_now()
        delta = now - start
        return delta.total_seconds()
```

---

## 📊 改善の優先順位

### Phase 1: 信頼性強化（Week 1）
1. ✅ ASCOM層エラーハンドリング → `core/ascom/telescope.py`
2. ✅ 抽象インターフェース → `core/ascom/interface.py`
3. ✅ 単位管理 → `config/constants.py`, `utils/units.py`
4. ✅ テストコード整理 → `tests/`フォルダ

### Phase 2: 機能補強（Week 2）
1. ✅ Slew遅延推定 → `_estimate_slew_time()`
2. ✅ PulseGuide補正 → `_execute_pulse_guide()`
3. ✅ 時刻同期 → `core/astronomy/time_sync.py`
4. ✅ Guider改善 → P/PID制御切り替え

### Phase 3: 実機テスト（Week 3-4）
1. ASCOM基本操作確認
2. ISS導入テスト
3. 短時間追尾テスト
4. 長時間安定性テスト

---

## 🔄 マイグレーション戦略

### ステップ1: インターフェース導入（互換性維持）
```python
# 既存コード
telescope = Telescope()

# 新規コード（互換）
mount: MountInterface = ASCOMTelescope()
```

### ステップ2: 機能ごとに新インターフェース対応
- `orbit.py` → 変更なし（skyfield継続使用）
- `tracker.py` → `MountInterface`対応
- `guider.py` → 単位管理統一

### ステップ3: テストコード統合
```
tests/
├── test_ascom_interface.py
├── test_tracking_*.py
```

---

## 🎯 次のアクション

1. **ASCOM検証（最優先）**
   - [ ] ドライバ設定画面で十字キー試行
   - [ ] ASCOM Python test script実行
   - [ ] `CanPulseGuide` プロパティ確認

2. **構造リファクタリング開始**
   - [ ] `core/ascom/interface.py` 作成
   - [ ] `core/ascom/telescope.py` に改善実装
   - [ ] `MountSimulator` を `MountInterface` 対応

3. **テストコード整備**
   - [ ] `tests/`フォルダ作成
   - [ ] 既存テストをここに移動

