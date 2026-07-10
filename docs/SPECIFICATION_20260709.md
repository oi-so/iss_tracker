# ISS追尾システム - 完全仕様書

**バージョン**: 2.0  
**作成日**: 2026-07-09  
**対象システム**: E-ZEUS II赤道儀 + Python ASCOM制御

---

## 📋 目次

1. [システム概要](#システム概要)
2. [アーキテクチャ](#アーキテクチャ)
3. [クラス仕様](#クラス仕様)
4. [モジュール仕様](#モジュール仕様)
5. [使用方法](#使用方法)
6. [トラブルシューティング](#トラブルシューティング)

---

## システム概要

### 目的

E-ZEUS II赤道儀をASCOM経由でPythonから制御し、リアルタイムでISS（国際宇宙ステーション）を自動追尾するシステム。

### 動作フロー

```
┌─────────────────────────────────────────────────┐
│  TLE (Two-Line Element) ダウンロード             │
│  → ISS軌道データ取得                             │
└──────────────────┬──────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  Skyfield ライブラリ                             │
│  → ISS軌道計算                                   │
│  → 観測地点から見たRA/Dec座標計算                 │
└──────────────────┬──────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  ASCOM Platform                                  │
│  → E-ZEUS IIドライバ経由で赤道儀制御              │
│  → GoTO（自動導入）                              │
│  → PulseGuide（ガイド補正）                      │
└──────────────────┬──────────────────────────────┘
                   ↓
┌──────────────────────────────────────────────────┐
│  赤道儀動作                                       │
│  → ISS導入（GoTO）                               │
│  → リアルタイム追尾（PulseGuide）                 │
└──────────────────────────────────────────────────┘
```

### 座標系

- **赤道座標系**: J2000（通常のASCOM仕様）
- **RA** (赤経): 0-24時間、または0-360度
- **Dec** (赤緯): -90 ~ +90度
- **内部計算**: 度（°）で統一
- **ASCOM入出力**: RA=時間, Dec=度

---

## アーキテクチャ

### レイヤー構成

```
┌─────────────────────────────────────┐
│  Application Layer (main.py)         │
│  ユーザーインターフェース            │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  ISS Tracking Layer                  │
│  (core/tracking/)                    │
│  ・ISSTracker: 追尾制御              │
│  ・Guider: ガイド補正生成           │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Astronomy Layer                     │
│  (core/astronomy/)                   │
│  ・OrbitCalculator: 軌道計算         │
│  ・TLELoader: TLE取得               │
│  ・TimeSync: 時刻同期               │
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Mount Interface Layer               │
│  (core/ascom/)                       │
│  ・MountInterface: 抽象基底          │
│  ・ASCOMTelescope: ASCOM実装        │
│  ・MountSimulator: テスト用シミュレータ│
└──────────────┬──────────────────────┘
               ↓
┌─────────────────────────────────────┐
│  Hardware Layer                      │
│  ・ASCOM Platform                    │
│  ・E-ZEUS IIドライバ                 │
│  ・赤道儀                           │
└─────────────────────────────────────┘
```

### 責務分離

| レイヤー | 責務 | 関連ファイル |
|---------|------|-----------|
| Application | ユーザー操作、タイミング制御 | main.py |
| Tracking | ISS追尾ロジック、補正計算 | tracker.py, guider.py |
| Astronomy | ISS軌道計算、座標変換 | orbit.py, tle.py |
| Mount Interface | 赤道儀の統一インターフェース | interface.py |
| Mount Implementation | ASCOM実装、通信 | telescope.py, mock.py |

---

## クラス仕様

### core/ascom/interface.py

#### Enum: `MountCapability`

赤道儀の利用可能な機能を表す

```python
class MountCapability(Enum):
    CAN_PULSE_GUIDE = 1   # PulseGuide対応
    CAN_MOVE_AXIS = 2     # MoveAxis対応
    CAN_SYNC = 4          # Sync対応
    CAN_SLEW = 8          # Slew対応
```

#### Enum: `GuideDirection`

ASCOM PulseGuideの方向定義

```python
class GuideDirection(Enum):
    NORTH = 0   # 北
    SOUTH = 1   # 南
    EAST = 2    # 東
    WEST = 3    # 西
```

#### Dataclass: `MountPosition`

赤道儀の位置

```python
@dataclass
class MountPosition:
    ra_hours: float        # 赤経 (0-24時間)
    dec_degrees: float     # 赤緯 (-90-90度)
```

#### Abstract Class: `MountInterface`

赤道儀の抽象インターフェース

**メソッド**:

| メソッド | 説明 | パラメータ | 戻り値 | 例外 |
|---------|------|-----------|--------|------|
| `connect()` | 接続 | なし | なし | RuntimeError |
| `disconnect()` | 切断 | なし | なし | なし |
| `is_connected()` | 接続状態 | なし | bool | なし |
| `get_position()` | 現在位置取得 | なし | MountPosition | RuntimeError |
| `slew_to_coordinates(ra, dec, async)` | GoTO実行 | RA(時間), Dec(度), 非同期フラグ | なし | RuntimeError, ValueError |
| `wait_slew(timeout)` | GoTO完了待機 | タイムアウト秒 | なし | RuntimeError, TimeoutError |
| `pulse_guide(dir, ms)` | PulseGuide | 方向, 継続時間ms | なし | RuntimeError, ValueError |
| `sync_to_coordinates(ra, dec)` | Sync | RA(時間), Dec(度) | なし | RuntimeError |
| `get_capabilities()` | 機能一覧 | なし | set[MountCapability] | なし |

**例**:

```python
mount: MountInterface = ASCOMTelescope()
mount.connect()

# 現在位置確認
pos = mount.get_position()
print(f"RA={pos.ra_hours:.4f}h, Dec={pos.dec_degrees:.4f}°")

# GoTO実行
mount.slew_to_coordinates(12.5, 45.0, async_=True)
mount.wait_slew()

# PulseGuide
mount.pulse_guide(GuideDirection.EAST, 100)

mount.disconnect()
```

---

### core/ascom/telescope.py

#### Class: `ASCOMTelescope(MountInterface)`

ASCOM E-ZEUS実装

**特徴**:
- ✅ エラーハンドリング完全実装
- ✅ COM例外を適切にキャッチ
- ✅ 機能自動検出
- ✅ 安全な属性アクセス

**メソッド** (interface.pyから継承):

すべて `MountInterface` で定義したメソッドを実装

**内部メソッド**:

```python
def _detect_capabilities() -> None:
    """機能検出"""
    # ドライバの Can* プロパティを確認

def _safe_getattr(obj, attr_name, default=False) -> Any:
    """ASCOM COMオブジェクトの安全な属性アクセス"""
```

**例**:

```python
telescope = ASCOMTelescope()
try:
    telescope.connect()
    print(f"機能: {telescope.get_capabilities()}")
except RuntimeError as e:
    print(f"エラー: {e}")
```

---

### core/ascom/mock.py

#### Class: `MountSimulator(MountInterface)`

テスト用シミュレータ

**特徴**:
- ✅ `MountInterface` と完全互換
- ✅ 実装と同じ使い方でテスト可能
- ✅ ガイド補正のシミュレーション
- ✅ `update(dt)` で時間進行

**追加メソッド**:

```python
def update(self, dt: float) -> None:
    """
    シミュレーション更新
    
    ガイド速度に基づいて位置を更新
    """
```

**使用例**:

```python
mount = MountSimulator()
mount.connect()
mount.slew_to_coordinates(12.0, 45.0)
mount.wait_slew()

# シミュレーション実行
for _ in range(100):
    mount.update(0.05)  # 50ms進行
```

---

### utils/units.py

#### Class: `CoordinateConverter`

座標単位変換ユーティリティ

**定数**:

```python
HOURS_TO_DEGREES = 15.0    # 1時間 = 15度
DEGREES_TO_HOURS = 1/15.0  # 1度 = 1/15時間
```

**メソッド**:

| メソッド | 入力 | 出力 | 説明 |
|---------|------|------|------|
| `ra_hours_to_degrees(h)` | RA時間 | RA度 | 赤経: 時間 → 度 |
| `ra_degrees_to_hours(d)` | RA度 | RA時間 | 赤経: 度 → 時間 |
| `normalize_ra_hours(h)` | RA時間 | RA時間 | 0-24に正規化 |
| `normalize_ra_degrees(d)` | RA度 | RA度 | 0-360に正規化 |
| `normalize_dec_degrees(d)` | Dec度 | Dec度 | -90-90に正規化 |

**例**:

```python
from utils.units import CoordinateConverter

# 変換
ra_deg = CoordinateConverter.ra_hours_to_degrees(12.5)  # 187.5

# 正規化
ra_h = CoordinateConverter.normalize_ra_hours(25.0)  # 1.0
dec_d = CoordinateConverter.normalize_dec_degrees(95.0)  # 90.0
```

---

### core/tracking/guider.py

#### Dataclass: `GuiderConfig`

ガイダー設定

```python
@dataclass
class GuiderConfig:
    kp: float = 0.05            # P制御ゲイン
    max_pulse_ms: int = 500     # 最大パルス時間
    dead_band_deg: float = 0.01 # デッドバンド
```

#### Class: `Guider`

ガイド補正コントローラー

**責務**:
- ISS速度から予測追尾速度を計算
- 位置誤差からP制御補正を計算
- 合計速度からPulseGuideパルスを生成・実行

**メソッド**:

```python
def __init__(self, mount: MountInterface, config: GuiderConfig = None) -> None:
    """初期化"""

def guide(
    self,
    ra_velocity_deg_per_sec: float,
    dec_velocity_deg_per_sec: float,
    ra_error_deg: float,
    dec_error_deg: float
) -> None:
    """
    ガイド補正実行
    
    Args:
        ra_velocity_deg_per_sec: ISS RA速度（度/秒）
        dec_velocity_deg_per_sec: ISS Dec速度（度/秒）
        ra_error_deg: RA位置誤差（度）
        dec_error_deg: Dec位置誤差（度）
    """
```

**内部動作**:

```python
# RA方向補正速度 = 予測速度 + P制御
ra_rate = ra_velocity + ra_error * kp

# 速度 → PulseGuide方向・継続時間に変換
if ra_rate > 0:
    direction = GuideDirection.EAST
else:
    direction = GuideDirection.WEST

duration_ms = int(abs(ra_rate) * 100)
mount.pulse_guide(direction, duration_ms)
```

**使用例**:

```python
guider = Guider(telescope)
guider.guide(
    ra_velocity_deg_per_sec=0.5,
    dec_velocity_deg_per_sec=0.2,
    ra_error_deg=0.1,
    dec_error_deg=-0.05
)
```

---

### core/tracking/tracker.py

#### Dataclass: `TrackingConfig`

追尾設定

```python
@dataclass
class TrackingConfig:
    pulse_interval_sec: float = 0.05   # パルス間隔
    max_slew_time_sec: float = 60.0    # Slew最大時間
    slew_padding_sec: float = 5.0      # 安全マージン
```

#### Class: `ISSTracker`

ISS追尾メインコントローラー

**責務**:
- ISS軌道計算
- 赤道儀制御
- ガイド制御の統合

**メソッド**:

```python
def __init__(
    self,
    mount: MountInterface,
    orbit: OrbitCalculator,
    guider: Guider = None,
    config: TrackingConfig = None
) -> None:
    """初期化"""

def acquire(self, target_time: datetime) -> None:
    """
    ISS自動導入
    
    現在位置からISS未来位置へGoTO実行
    
    Args:
        target_time: 目標時刻（UTC）
    
    処理フロー:
      1. 現在位置確認
      2. ISS現在位置計算
      3. Slew時間推定
      4. ISS未来位置計算
      5. GoTO実行
      6. 完了待機
    """

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
    
    処理フロー（周期反復）:
      1. ISS現在位置計算
      2. ISS未来位置計算（速度算出）
      3. 赤道儀現在位置取得
      4. 誤差計算
      5. ガイド補正実行
      6. 次の周期まで待機
    """

def stop_tracking(self) -> None:
    """追尾停止"""

def _estimate_slew_time(
    self,
    from_ra_deg: float,
    from_dec_deg: float,
    to_ra_deg: float,
    to_dec_deg: float
) -> float:
    """
    Slew時間推定
    
    角度差から推定時間を計算
    """
```

**使用例**:

```python
tracker = ISSTracker(telescope, orbit, guider)

# ISS導入
from datetime import datetime, timezone
now = datetime.now(timezone.utc)
tracker.acquire(now)

# 追尾開始
tracker.start_tracking(now, duration_sec=300)  # 5分間
```

---

## モジュール仕様

### 既存モジュール (保持 / 後で移動予定)

#### tle.py → core/astronomy/tle_loader.py

TLE取得

```python
class TLELoader:
    def update(self) -> None:
        """最新TLEをダウンロード"""
        # requests経由でCelestrak取得
        
    @property
    def satellite(self) -> EarthSatellite:
        """Skyfield EarthSatelliteオブジェクト"""
```

#### orbit.py → core/astronomy/orbit_calculator.py

ISS軌道計算

```python
class OrbitCalculator:
    def __init__(self, satellite: EarthSatellite) -> None:
        """初期化"""
        self.ts = load.timescale()  # Skyfield timescale
        self.satellite = satellite
        
    def get_position(self, t: Time = None) -> ISSPosition:
        """現在時刻（またはt）のISS位置取得"""
        
    def get_position_after(self, base_time: Time, seconds: float) -> ISSPosition:
        """base_time + seconds秒後のISS位置"""
        
    def get_position_at(self, t: Time) -> ISSPosition:
        """指定時刻のISS位置"""
```

**戻り値**: `ISSPosition`

```python
@dataclass
class ISSPosition:
    time: Time              # Skyfield Time
    ra: Angle              # 赤経
    dec: Angle             # 赤緯
    distance: Distance     # 距離
    altitude: Angle        # 地平座標高度
    azimuth: Angle         # 地平座標方位角
```

---

## 使用方法

### 基本的な追尾プログラム

```python
from datetime import datetime, timezone
from core.ascom.telescope import ASCOMTelescope
from core.tracking.tracker import ISSTracker, TrackingConfig
from core.tracking.guider import Guider
from core.astronomy.orbit_calculator import OrbitCalculator
from core.astronomy.tle_loader import TLELoader

def main():
    # 初期化
    tle = TLELoader()
    tle.update()
    
    orbit = OrbitCalculator(tle.satellite)
    telescope = ASCOMTelescope()
    telescope.connect()
    
    guider = Guider(telescope)
    config = TrackingConfig(pulse_interval_sec=0.05)
    tracker = ISSTracker(telescope, orbit, guider, config)
    
    try:
        # ISS導入
        now = datetime.now(timezone.utc)
        tracker.acquire(now)
        
        # 追尾開始（5分間）
        tracker.start_tracking(now, duration_sec=300)
        
    except KeyboardInterrupt:
        tracker.stop_tracking()
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        telescope.disconnect()

if __name__ == "__main__":
    main()
```

### シミュレーション実行

```python
from core.ascom.mock import MountSimulator
from core.tracking.tracker import ISSTracker
from core.astronomy.orbit_calculator import OrbitCalculator
from core.astronomy.tle_loader import TLELoader
from datetime import datetime, timezone

tle = TLELoader()
tle.update()

orbit = OrbitCalculator(tle.satellite)
mount = MountSimulator()
mount.connect()

tracker = ISSTracker(mount, orbit)

now = datetime.now(timezone.utc)
tracker.start_tracking(now, duration_sec=30)

mount.disconnect()
```

---

## トラブルシューティング

### Q1: ASCOM接続に失敗

**症状**: `RuntimeError: ドライバの初期化に失敗`

**原因**: 
- ASCOM Platformがインストールされていない
- E-ZEUS Telescopeドライバがインストールされていない
- COM接続が他プロセスで使用中

**対策**:
```python
1. ASCOM Platform再インストール
2. E-ZEUS IIドライバ再インストール
3. COMポート設定確認
4. SUPER STAR IV等との同時接続を避ける
```

### Q2: 座標が実際の赤道儀方向と異なる

**症状**: `座標差 > 180°`

**原因**:
- SUPER STAR IVでの位置合わせがされていない
- ASCOMドライバが座標を保持していない

**対策**:
```python
# SUPER STAR IVで位置合わせを実施後、
# Python実行前にASCOMドライバを起動確認

# またはPythonで同期実行
telescope.sync_to_coordinates(known_ra_h, known_dec_d)
```

### Q3: PulseGuideが実行されない

**症状**: 赤道儀が微小補正で動かない

**原因**:
- ドライバが `CanPulseGuide=False`
- パルス継続時間が0ms
- Guiderの速度 → パルス時間変換が不適切

**対策**:
```python
# 機能確認
print(telescope.get_capabilities())
# → MountCapability.CAN_PULSE_GUIDE が含まれているか確認

# パラメータ調整
guider_config = GuiderConfig(
    kp=0.05,           # P制御ゲインを調整
    max_pulse_ms=500,  # 最大パルス時間を調整
    dead_band_deg=0.01 # デッドバンドを調整
)
```

### Q4: ISS導入に失敗

**症状**: `TimeoutError: Slew完了タイムアウト`

**原因**:
- Slew時間推定が短すぎる
- 赤道儀のSlew速度が遅い

**対策**:
```python
config = TrackingConfig(
    max_slew_time_sec=120.0,   # 最大Slew時間を延長
    slew_padding_sec=10.0,      # 安全マージン追加
)
```

### Q5: 追尾が不安定

**症状**: 赤道儀が震える、位置がドリフト

**原因**:
- P制御ゲインが大きすぎる
- ガイド感度の仮定値が実際と異なる
- パルス間隔が短すぎる

**対策**:
```python
# P制御ゲイン低下
config = GuiderConfig(kp=0.02)  # デフォルト 0.05

# パルス間隔延長
tracking_config = TrackingConfig(pulse_interval_sec=0.1)  # デフォルト 0.05

# 赤道儀の実際のガイド感度を測定し、
# Guider._execute_pulse_guide() の変換式を調整
# 現在: duration_ms = int(abs(rate) * 100)
```

---

## 参考資料

- **ASCOM Platform**: https://ascom-standards.org/
- **Skyfield**: https://rhodesmill.org/skyfield/
- **E-ZEUS II**: https://www.tmb.jp/
- **CelesTrak**: https://celestrak.org/

---

## ライセンス

このプロジェクトはMIT Licenseの下で公開されています。

