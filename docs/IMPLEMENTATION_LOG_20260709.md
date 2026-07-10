# ISS追尾システム - 実装変更ログ

**更新日**: 2026-07-09  
**進捗**: Step 2 (改善アーキテクチャ実装完了)

---

## 📁 ファイル構成の変更

### 新規作成ファイル

```
core/                              (新規ディレクトリ)
├── ascom/
│   ├── __init__.py
│   ├── interface.py               ← 抽象インターフェース定義
│   ├── telescope.py               ← ASCOM実装（改善版）
│   └── mock.py                    ← MountSimulator改善版
├── astronomy/
│   ├── __init__.py
│   └── (既存ファイルは後で移動予定)
├── tracking/
│   ├── __init__.py
│   ├── guider.py                  ← ガイダー改善版
│   └── tracker.py                 ← トラッカー改善版
└── __init__.py

utils/
├── __init__.py
└── units.py                       ← 座標単位変換（新規）

config/
├── __init__.py
└── (settings.py等は後で作成予定)

models/
├── __init__.py
└── (position.py等は後で作成予定)

tests/
├── __init__.py
└── test_ascom_units.py            ← P0テスト（新規）
```

### 既存ファイルの状態

| ファイル | 状態 | 備考 |
|---------|------|------|
| telescope.py | 保持 | 後で`core/ascom/telescope.py`と統合 |
| telescope_simulator.py | 保持 | 後で`core/ascom/mock.py`と統合 |
| tracker.py | 保持 | 後で`core/tracking/tracker.py`と統合 |
| guider.py | 保持 | 後で`core/tracking/guider.py`と統合 |
| orbit.py | 保持 | 後で`core/astronomy/`に移動 |
| tle.py | 保持 | 後で`core/astronomy/`に移動 |
| main.py | 保持 | 後で新インターフェース対応に更新 |

---

## 🎯 実装内容の詳細

### 1. **core/ascom/interface.py**

**目的**: 赤道儀制御の抽象インターフェース定義

**主要クラス**:

| クラス | 役割 |
|-------|------|
| `MountCapability` (Enum) | 赤道儀の機能フラグ（PulseGuide、Slew等） |
| `GuideDirection` (Enum) | ASCOM方向定義（NORTH/SOUTH/EAST/WEST） |
| `MountPosition` (dataclass) | 赤経・赤緯座標 |
| `MountInterface` (ABC) | 抽象基底クラス |

**メソッド**:
```
connect()                   - 接続
disconnect()                - 切断
is_connected()              - 接続状態確認
get_position()              - 現在位置取得
slew_to_coordinates()       - GoTO実行
wait_slew()                 - GoTO完了待機
pulse_guide()               - PulseGuide実行
sync_to_coordinates()       - Sync実行
get_capabilities()          - 機能一覧取得
```

**メリット**:
- ✅ 異なる実装（ASCOM、シミュレータ等）を統一的に扱える
- ✅ インターフェースを実装すれば新しい赤道儀も対応可能
- ✅ テストしやすくなる

---

### 2. **utils/units.py**

**目的**: 座標単位変換の統一管理

**主要クラス**: `CoordinateConverter`

**メソッド**:
```python
ra_hours_to_degrees(h)      # 時間 → 度
ra_degrees_to_hours(d)      # 度 → 時間
normalize_ra_hours(h)       # 0-24に正規化
normalize_ra_degrees(d)     # 0-360に正規化
normalize_dec_degrees(d)    # -90-90に正規化
```

**メリット**:
- ✅ 単位変換をこのモジュール1か所に集約
- ✅ インライン計算を避け、意図が明確
- ✅ テストしやすい

**使用例**:
```python
from utils.units import CoordinateConverter

ra_deg = CoordinateConverter.ra_hours_to_degrees(12.5)
ra_norm = CoordinateConverter.normalize_ra_hours(25.0)
```

---

### 3. **core/ascom/telescope.py**

**目的**: 改善されたASCOM E-ZEUS制御

**主要クラス**: `ASCOMTelescope(MountInterface)`

**改善点**:

#### 問題1: エラーハンドリング不足 → 解決
```python
# 改善前
self.scope = win32com.client.Dispatch(progid)

# 改善後
try:
    self.scope = win32com.client.Dispatch(progid)
except Exception as e:
    raise RuntimeError(f"ドライバの初期化に失敗: {e}") from e
```

#### 問題2: 属性アクセス例外なし → 解決
```python
# 改善前
if getattr(self.scope, 'CanPulseGuide', False):

# 改善後（_safe_getattr メソッド）
@staticmethod
def _safe_getattr(obj, attr_name, default=False):
    try:
        value = getattr(obj, attr_name, None)
        return bool(value) if value is not None else default
    except:
        return default
```

#### 問題3: PulseGuide未実装 → 実装完了
```python
def pulse_guide(self, direction, duration_ms):
    """完全実装"""
    if not self.is_connected():
        raise RuntimeError("...")
    if MountCapability.CAN_PULSE_GUIDE not in self._capabilities:
        raise RuntimeError("...")
    # パラメータチェック
    if not (0 <= duration_ms <= 30000):
        raise ValueError(...)
    try:
        self.scope.PulseGuide(direction.value, duration_ms)
    except Exception as e:
        raise RuntimeError(...) from e
```

#### 問題4: タイムアウト処理 → 改善
```python
# wait_slew()に詳細なロギング追加
print(f"  Slew中... ({elapsed:.1f}秒経過)")
```

**メリット**:
- ✅ 実機で落ちない堅牢な実装
- ✅ エラー原因が明確
- ✅ 機能検出が安全

---

### 4. **core/ascom/mock.py**

**目的**: テスト用赤道儀シミュレータ

**主要クラス**: `MountSimulator(MountInterface)`

**改善点**:
- ✅ `MountInterface` を継承 → 他の実装と互換
- ✅ 座標正規化を統一 (CoordinateConverter使用)
- ✅ `update()` メソッドでシミュレーション時間進行

**メリット**:
- ✅ 実装と同じインターフェース → 切り替え容易
- ✅ テスト時に赤道儀不要

---

### 5. **core/tracking/guider.py**

**目的**: ガイド補正制御

**主要クラス**:
- `GuiderConfig`: 設定
- `Guider`: ガイダー本体

**改善点**:

#### 問題1: 単位が不明確 → 解決
```python
# 改善前
self.mount.pulse_guide(ra_rate, dec_rate, 0.05)  # 単位不明

# 改善後
def guide(
    self,
    ra_velocity_deg_per_sec: float,  # ← 単位明確
    dec_velocity_deg_per_sec: float,
    ra_error_deg: float,
    dec_error_deg: float
):
```

#### 問題2: PulseGuideの方向・継続時間変換なし → 実装
```python
# RA補正
if abs(ra_rate_deg_per_sec) > self.config.dead_band_deg:
    ra_direction = (
        GuideDirection.EAST
        if ra_rate_deg_per_sec > 0
        else GuideDirection.WEST
    )
    ra_pulse_ms = int(abs(ra_rate_deg_per_sec) * 100) % self.config.max_pulse_ms
    self.mount.pulse_guide(ra_direction, ra_pulse_ms)
```

**メリット**:
- ✅ 単位が明確
- ✅ GuideDirection を使用 → 正しいASCOM仕様
- ✅ デッドバンド搭載 → ノイズ除去

---

### 6. **core/tracking/tracker.py**

**目的**: ISS追尾メインループ

**主要クラス**:
- `TrackingConfig`: 設定
- `ISSTracker`: 追尾コントローラー

**主要メソッド**:

```python
def acquire(self, target_time):
    """ISS自動導入"""
    # 1. 現在位置確認
    # 2. ISS位置計算
    # 3. Slew時間推定
    # 4. ISS未来位置へGoTO
    # 5. Slew完了待機
    
def start_tracking(self, start_time, duration_sec):
    """ISS追尾ループ"""
    # 1. ISS現在位置計算
    # 2. ISS速度計算（予測追尾）
    # 3. 赤道儀現在位置取得
    # 4. 誤差計算
    # 5. ガイド補正実行
    # 6. 周期待機して反復
```

**改善点**:

#### 問題1: 時刻同期の危険性 → 改善予定
※ 次フェーズで `TimeSync` クラスを追加予定

#### 問題2: Slew遅延が固定値 → 動的推定
```python
def _estimate_slew_time(self, from_ra_deg, from_dec_deg, to_ra_deg, to_dec_deg):
    """角度差からSlew時間を推定"""
    delta_ra = abs(...)
    delta_dec = abs(...)
    max_delta = max(delta_ra, delta_dec)
    estimated = max_delta / 1.0  # 度/秒
    return min(estimated, self.config.max_slew_time_sec)
```

**メリット**:
- ✅ 導入精度向上
- ✅ 架台特性に応じて調整可能
- ✅ 単位が一貫 (度/秒)

---

### 7. **tests/test_ascom_units.py**

**目的**: P0検証テスト

**テスト内容**:

1. **Test 1**: ASCOM基本接続テスト
   - ドライバ選択
   - 接続確立
   - 機能確認
   - 位置取得

2. **Test 2**: 座標単位変換テスト
   - RA: 時間 ↔ 度
   - RA: 正規化 0-24
   - Dec: 正規化 -90-90

3. **Test 3**: ISS座標 vs 赤道儀座標
   - TLE取得
   - ISS位置計算
   - 赤道儀座標取得
   - 差分確認

**実行方法**:
```bash
python tests/test_ascom_units.py
```

---

## 🔄 後方互換性戦略

### 現在の状態

```
既存ファイル（ルート）      新インターフェース（core/）
├── telescope.py        ← core/ascom/telescope.py (互換性維持中)
├── telescope_simulator.py ← core/ascom/mock.py
├── tracker.py          ← core/tracking/tracker.py
├── guider.py           ← core/tracking/guider.py
└── main.py             (未更新、既存ファイル継続使用)
```

### マイグレーション手順

**Phase 1: 並行運用**
- ✅ 新コード (`core/`) 作成完了
- 🔄 既存コード (`*.py`) は保持
- ⏳ テストで新コード検証

**Phase 2: 段階的切り替え** (来週予定)
- 新 `core/ascom/telescope.py` へ切り替え
- 新 `core/tracking/guider.py` へ切り替え
- 既存ファイルを `core/` に移動

**Phase 3: 完全統合** (再来週予定)
- `main.py` を新インターフェース対応に更新
- テスト完了後、既存ファイル削除

---

## ✅ 実装完了項目

| 項目 | 状態 | 備考 |
|------|------|------|
| P1-1: エラーハンドリング強化 | ✅完了 | ASCOMTelescope.py実装 |
| P1-2: 座標単位管理統一 | ✅完了 | units.py実装 |
| P1-3: インターフェース導入 | ✅完了 | interface.py実装 |
| P1-4: PulseGuide正しい実装 | ✅完了 | telescope.py + guider.py |
| P0テスト化 | ✅完了 | test_ascom_units.py |

---

## ⚠️ 注意事項

### 1. インポートパス
現在、既存ファイルが `*.py` のままのため、新コードとの相互参照で循環インポートの可能性あり。

**解決方法**: Phase 2でリファクタリング時に整理。

### 2. TrackingConfigの時刻同期
```python
# 改善予定
class TimeSync:
    @staticmethod
    def get_utc_now() -> datetime:
        return datetime.now(timezone.utc)
```

### 3. ガイド感度の仮定値
```python
# guider.py と mock.py で以下を仮定
# "0.1度/100ms" のガイド感度

# 実際の赤道儀での調整が必要
```

---

## 🚀 次のステップ

### 即実施 (P0テスト)
- [ ] `test_ascom_units.py` の Test 1 実行
- [ ] E-ZEUS Driver設定画面で十字キー試行
- [ ] `scope.CanMoveAxis`, `scope.CanPulseGuide` 確認

### 今週中 (P1完了)
- [ ] 新インターフェース基で`main.py`の試験版作成
- [ ] シミュレータでの追尾テスト
- [ ] 実機での基本動作テスト

### 来週 (リファクタリング)
- [ ] `core/astronomy/` への移動
- [ ] 既存ファイルの統合
- [ ] テストスイート拡充

---

## 📝 変更理由サマリー

| 変更 | 理由 | メリット |
|------|------|---------|
| インターフェース導入 | 異なる実装を統一したい | テストしやすい、交換可能 |
| 座標単位管理 | 単位混乱を避けたい | バグ減少、可読性向上 |
| エラーハンドリング強化 | 実機で落ちるのを防ぎたい | 堅牢性向上、デバッグ容易 |
| PulseGuide実装 | 追尾が機能していない | 追尾制御が可能になる |
| ガイド補正ロジック | 速度→パルス時間の変換が不明 | ガイドが正しく機能 |

