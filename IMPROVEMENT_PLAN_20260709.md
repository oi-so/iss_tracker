# ISS追尾システム - 修正計画（優先度付き）

**作成日**: 2026-07-09  
**進捗**: Step 1 (分析完了)

---

## 🎯 全体方針

1. **段階的な改善**: 小さな変更を積み重ねる
2. **後方互換性**: 既存テストが動き続けることを確保
3. **検証重視**: 各変更後に動作確認
4. **ドキュメント**: 同時進行で仕様書作成

---

## 📋 修正タスク一覧（優先度順）

### 🔴 **P0: 致命的・検証必須** (即実施)

#### P0-1: ASCOM接続検証
**目的**: ASCOM経由の移動命令が実際に赤道儀を動かすか確認

**実施内容**:
```
□ E-ZEUS Driverの設定画面を開く
□ ドライバの十字キー操作で赤道儀が動くか確認
□ ASCOM Driver Checkツール実行（使用可能なら）
□ Python: scope.CanMoveAxis プロパティ確認
□ Python: MoveAxis() テスト実行
□ 座標取得後、実際の望遠鏡方向と一致か確認
```

**修正ファイル**: `mount_test.py` をテストツール化

**成功条件**:
- [ ] ドライバ十字キー → 赤道儀動く
- [ ] scope.CanMoveAxis == True
- [ ] 取得座標が実際の方向と一致

**失敗時の次ステップ**:
1. COMポート設定確認
2. ドライバ再インストール
3. SUPER STAR IVで同じCOMポートが動作確認

---

#### P0-2: ASCOM RA/Dec単位の完全確認
**目的**: 座標系・単位の不安を解消

**実施内容**:
```python
# 新規ファイル: test_ascom_units.py

# 既知の座標（北極星など）に向かせる
# SUPER STAR IVと Python の座標を比較

skyfield_time = ...
iss_pos = orbit.get_position_at(skyfield_time)

print(f"ISS RA: {iss_pos.ra.hours:.4f}h = {iss_pos.ra.degrees:.4f}°")
print(f"ISS Dec: {iss_pos.dec.degrees:.4f}°")

# Telephoneで取得
ra_h, dec_d = telescope.get_position()
print(f"Telescope RA: {ra_h:.4f}h = {ra_h*15:.4f}°")
print(f"Telescope Dec: {dec_d:.4f}°")

# 差分確認
```

**修正ファイル**: 新規 `test_ascom_units.py`

**成功条件**:
- [ ] RA単位が一貫性
- [ ] Dec単位が一貫性
- [ ] Skyfield vs Telescope 座標差 < 1°（初期状態の誤差は許容）

---

### 🟡 **P1: 高優先度** (このWeek内に完了)

#### P1-1: ASCOM層エラーハンドリング強化
**目的**: 実機運用時のクラッシュを防止

**修正箇所**:

| 位置 | 現在 | 改善内容 | 影響度 |
|------|------|--------|--------|
| `telescope.py:connect()` | try-except最小限 | COM例外→詳細メッセージ | 高 |
| `telescope.py:get_position()` | スコープのアクセス例外なし | try-except追加 | 高 |
| `telescope.py:wait_slew()` | Slewing例外対応なし | try-except追加 | 中 |
| `telescope.py:pulse_guide()` | 未実装 | 完全実装+例外 | 高 |

**修正コード例**:
```python
def connect(self):
    try:
        chooser = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
    except Exception as e:
        raise RuntimeError(f"ASCOM Utilities初期化失敗: {e}") from e
    
    try:
        self.scope = win32com.client.Dispatch(progid)
        self.scope.Connected = True
    except Exception as e:
        self.scope = None
        raise RuntimeError(f"ドライバ接続失敗 ({progid}): {e}") from e
```

**修正ファイル**: `telescope.py`

**テスト方法**:
```python
# test_ascom_errors.py
try:
    telescope.connect()  # ドライバなし状態
except RuntimeError as e:
    print(e)  # 詳細メッセージ表示確認
```

---

#### P1-2: 座標単位管理の統一
**目的**: 内部コードの混乱を減らす

**実施内容**:

```
新規ファイル: utils/units.py

CoordinateConverter クラス:
  - ra_hours_to_degrees(h) → 度
  - ra_degrees_to_hours(d) → 時間
  - normalize_ra_hours(h) → 0-24
  - normalize_dec_degrees(d) → -90-90
```

**使用例**:
```python
from utils.units import CoordinateConverter

# 変換
ra_deg = CoordinateConverter.ra_hours_to_degrees(12.5)  # 187.5

# 正規化
ra = CoordinateConverter.normalize_ra_hours(25.0)  # 1.0
```

**修正ファイル**:
- 新規: `utils/__init__.py`, `utils/units.py`
- 更新: `tracker.py`, `telescope_simulator.py`, `orbit.py`

**変更影響**:
- `tracker.py`: ra速度計算で使用 (小規模)
- `telescope_simulator.py`: goto時に使用 (小規模)
- その他: 互換性維持

---

#### P1-3: インターフェース・抽象化導入
**目的**: テストしやすい構造へ

**実施内容**:

```
新規ファイル: core/ascom/interface.py
  - MountInterface (ABC)
  - MountCapability (Enum)
  - GuideDirection (Enum)

変更: telescope.py
  - MountInterface を継承

変更: telescope_simulator.py
  - MountInterface を継承
```

**作業量**: 中程度 (1-2時間)

**修正ファイル**:
- 新規: `core/__init__.py`, `core/ascom/__init__.py`, `core/ascom/interface.py`
- 更新: `telescope.py` (implements追加)
- 更新: `telescope_simulator.py` (implements追加)

**互換性**: ✅ 完全互換（既存コード変更なし）

---

#### P1-4: PulseGuide 正しい実装
**目的**: ガイド制御が機能するようにする

**現在の問題**:
```python
# guider.py - 呼び出し先がない
self.mount.pulse_guide(ra_rate, dec_rate, 0.05)

# telescope.py - 空実装
def pulse_guide(self, direction, duration_ms):
    if self.simulate:
        print("PulseGuide ...")
        return
    # ← 実装がない！
```

**正しい実装**:
```python
# core/ascom/interface.py の GuideDirection 使用

def pulse_guide(self, direction: GuideDirection, duration_ms: int):
    """
    direction: GuideDirection.NORTH/SOUTH/EAST/WEST
    duration_ms: 0-30000ms
    """
    if not self.is_connected():
        raise RuntimeError("未接続")
    
    try:
        self.scope.PulseGuide(direction.value, duration_ms)
    except Exception as e:
        raise RuntimeError(f"PulseGuide失敗: {e}") from e
```

**Guider側の修正**:
```python
# guider.py
from core.ascom.interface import GuideDirection

def guide(self, ra_velocity, dec_velocity, ra_error, dec_error):
    # 速度 + 誤差補正
    ra_rate = ra_velocity + ra_error * self.kp
    dec_rate = dec_velocity + dec_error * self.kp
    
    # RA方向決定
    if abs(ra_rate) > 0.01:
        direction = GuideDirection.EAST if ra_rate > 0 else GuideDirection.WEST
        duration_ms = int(abs(ra_rate) * 100)  # 速度 → 時間変換
        self.mount.pulse_guide(direction, duration_ms)
    
    # Dec方向決定
    if abs(dec_rate) > 0.01:
        direction = GuideDirection.NORTH if dec_rate > 0 else GuideDirection.SOUTH
        duration_ms = int(abs(dec_rate) * 100)
        self.mount.pulse_guide(direction, duration_ms)
```

**修正ファイル**:
- 更新: `telescope.py` (pulse_guide実装)
- 更新: `guider.py` (GuideDirection使用、単位変換)

**テスト**:
```python
# test_pulse_guide.py
telescope.pulse_guide(GuideDirection.EAST, 100)  # OK
telescope.pulse_guide(GuideDirection.NORTH, 50)   # OK
```

---

### 🟢 **P2: 中優先度** (来週以降)

#### P2-1: 時刻同期の改善
**目的**: `perf_counter()`による誤差排除

**現在**:
```python
# tracker.py
start_real = time.perf_counter()
elapsed = time.perf_counter() - start_real
```

**改善**:
```python
# core/astronomy/time_sync.py
from datetime import datetime, timezone

start_time = datetime.now(timezone.utc)
elapsed = TimeSync.elapsed_seconds(start_time)
```

**修正ファイル**:
- 新規: `core/astronomy/time_sync.py`
- 更新: `tracker.py`, `main.py`

**影響度**: 低 (同期精度向上のみ)

---

#### P2-2: Slew遅延の動的推定
**目的**: GoTo時間を正確に予測

**現在**:
```python
# main.py
goto_delay = 20  # 固定値
```

**改善**:
```python
# core/tracking/tracker.py
def _estimate_slew_time(self, from_ra, from_dec, to_time):
    # 角度差から遅延推定
    # 実際のslew速度パラメータ化
```

**修正ファイル**:
- 新規: `core/tracking/tracker.py` (ISSTracker)
- 更新: `main.py`

**影響度**: 中 (ISS導入精度向上)

---

#### P2-3: アーキテクチャリファクタリング
**目的**: テストしやすい構造に

**移動**:
```
tle.py                  → core/astronomy/tle_loader.py
orbit.py                → core/astronomy/orbit_calculator.py
predictor.py            → core/astronomy/predictor.py

telescope.py            → core/ascom/telescope.py
telescope_simulator.py  → core/ascom/mock.py

tracker.py              → core/tracking/tracker.py
guider.py               → core/tracking/guider.py

mount_test.py           → tests/test_mount.py
check.py                → tests/test_ascom.py
test.py                 → tests/test_tracker.py
```

**新規フォルダ**:
```
core/
  __init__.py
  astronomy/
    __init__.py
    tle_loader.py
    orbit_calculator.py
    predictor.py
    coordinate_transform.py
    time_sync.py
  ascom/
    __init__.py
    interface.py
    telescope.py
    mock.py
  tracking/
    __init__.py
    tracker.py
    guider.py
    safety.py

config/
  __init__.py
  settings.py
  constants.py

utils/
  __init__.py
  units.py

tests/
  __init__.py
  test_ascom.py
  test_astronomy.py
  test_tracking.py

models/
  __init__.py
  position.py
  error.py
```

**影響度**: 大 (すべてのインポート更新必要)

**実施タイミング**: リファクタリングはP1, P2-1, P2-2を完了後

---

### 🔵 **P3: 低優先度** (実機テスト後)

#### P3-1: 安全装置（Safetyモジュール）
```python
# core/tracking/safety.py

- 架台可動範囲チェック (HA制限など)
- 高度チェック (地平線以下か判定)
- 速度上限 (最大Slew速度超過検出)
```

---

#### P3-2: ロギング・監視
```python
# utils/logger.py

- 追尾ログ記録
- エラーログ記録
- パフォーマンス分析
```

---

#### P3-3: 設定ファイル化
```
config/settings.py

観測地点、パラメータをJSONまたはYAMLで管理
```

---

## 🔄 実施ロードマップ

### **Week 1 (今週)**

```
□ P0-1: ASCOM接続検証        (2時間)
□ P0-2: 単位確認テスト        (1時間)
□ P1-1: エラーハンドリング    (2時間)
□ P1-2: 座標単位管理          (1.5時間)
□ P1-3: インターフェース導入  (2時間)
□ P1-4: PulseGuide実装       (1.5時間)

合計: 約10時間
```

### **Week 2**

```
□ P1-4: PulseGuide テスト    (1時間)
□ P2-1: 時刻同期改善         (1時間)
□ P2-2: Slew遅延推定         (1.5時間)
□ 実機テスト準備             (2時間)

合計: 約5.5時間
```

### **Week 3-4**

```
□ 実機テスト実施
□ ISS導入テスト
□ 短時間追尾テスト
□ 長時間安定性テスト
```

---

## ✅ 成功基準

### **Phase 1 終了時**
- [ ] ASCOM接続が赤道儀を実際に動かす
- [ ] 座標単位に一貫性がある
- [ ] エラーハンドリングが堅牢
- [ ] PulseGuideが機能する

### **Phase 2 終了時**
- [ ] 時刻同期が正確
- [ ] ISS導入が精度5°以内
- [ ] 追尾ループが安定動作

### **Phase 3 終了時**
- [ ] リアルタイムISS追尾成功
- [ ] 過去・未来のISS追尾可能
- [ ] ドキュメント完成

---

## 📝 次のアクション（即実施）

1. **ASCOM検証（最優先）**
   ```
   □ E-ZEUS Driver設定画面を開く
   □ 十字キーで赤道儀操作試行
   ```

2. **P0タスク実施**
   ```
   □ mount_test.py を改良
   □ test_ascom_units.py 作成
   ```

3. **P1-1 実装開始**
   ```
   □ telescope.py にエラーハンドリング追加
   ```

