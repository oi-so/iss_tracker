# ISS Tracker 開発メモ

最終更新: 2026-07-09

---

# プロジェクト概要

SkyfieldでISSの軌道を計算し、ASCOM経由でE-ZEUS IIを制御してISSを自動追尾するソフトウェアを開発する。

最終目標

```
Skyfield
      ↓
ISS軌道計算
      ↓
ASCOM
      ↓
E-ZEUS II
      ↓
赤道儀
      ↓
Sony α7III
```

さらに最終的には

```
Skyfield
      ↓
予測位置
      ↓
OpenCVでISS検出
      ↓
位置誤差
      ↓
PulseGuide
```

による閉ループ制御を行う。

---

# 現在の進捗

## 完了

- TLE取得
- SkyfieldによるISS位置計算
- 観測地点補正
- Predictor
- 未来位置計算
- 予測軌跡生成

## 未実装

- PassPredictor
- ASCOM接続
- PulseGuide制御
- GUI
- OpenCV画像認識
- 自動補正

---

# フォルダ構成

```
iss_tracker/
│
├── config.py
├── models.py
├── tle.py
├── orbit.py
├── predictor.py
├── mount.py      # 未実装
├── main.py
└── requirements.txt
```

---

# requirements.txt

```
skyfield
requests
pywin32
```

---

# config.py

役割

- 観測地点
- URL
- 今後設定を書く

現在

```
OBSERVER
TLE_URL
```

---

# models.py

役割

ISSの位置を保持する。

```
ISSPosition
```

保持するデータ

```
time
ra
dec
distance
altitude
azimuth
```

---

# tle.py

役割

ISSの最新TLEを取得する。

使用方法

```python
loader = TLELoader()

loader.update()

satellite = loader.satellite
```

公開メソッド

```
update()
```

---

# orbit.py

役割

Skyfieldを用いてISS位置を計算する。

公開メソッド

```
get_position()

現在時刻の位置を返す
```

```
get_position_after(base_time, seconds)

base_timeからseconds秒後の位置を返す
```

内部メソッド

```
_calc(Time)

SkyfieldのTimeからISSPositionを生成
```

使用例

```python
orbit = OrbitCalculator(satellite)

pos = orbit.get_position()
```

未来位置

```python
base = orbit.ts.now()

future = orbit.get_position_after(
    base,
    5.0
)
```

---

# predictor.py

役割

未来位置を一定間隔で生成する。

公開メソッド

```
predict(duration, interval)
```

引数

```
duration

予測時間[s]
```

```
interval

計算間隔[s]
```

戻り値

```
list[ISSPosition]
```

使用例

```python
predictor = Predictor(orbit)

positions = predictor.predict(
    duration=30,
    interval=0.1,
)
```

返されるデータ

```
0.0秒後

0.1秒後

0.2秒後

・・・

30.0秒後
```

---

# mount.py

未実装

将来的には

```
connect()

disconnect()

goto()

pulse_guide()

move_axis()

sync()
```

を実装予定。

---

# main.py

動作確認用。

現在

```
Predictorを実行

↓

位置を表示
```

---

# 現在のデータの流れ

```
TLE取得

↓

EarthSatellite

↓

OrbitCalculator

↓

ISSPosition

↓

Predictor

↓

list[ISSPosition]
```

---

# ASCOM

## 必要なもの

- ASCOM Platform
- E-ZEUS Telescope Driver
- pywin32

ASCOM Chooserでは

```
EZEUS Telescope
```

を選択する。

---

# E-ZEUS Driver

確認済み機能

- Sync
- ReSync
- PulseGuide
- 恒星時停止
- カメラ方向補正

PulseGuide対応であることを確認済み。

---

# 今後実装予定

## PassPredictor

役割

ISSが見える時間を計算する。

返すデータ

```
出現時刻

最高高度

最高高度時刻

消失時刻
```

使用例

```python
passes = predictor.find_passes(...)
```

---

## Mount

ASCOM接続

```
connect()

↓

現在座標取得

↓

CanPulseGuide取得

↓

CanMoveAxis取得
```

---

## Tracking

```
Skyfield

↓

ISS位置

↓

現在位置との差

↓

PulseGuide
```

---

## Camera

Sony α7III

↓

OpenCV

↓

ISS検出

↓

誤差

↓

PulseGuide
```

---

# 将来のフォルダ構成（予定）

```
iss_tracker/
│
├── config.py
├── models.py
│
├── orbit.py
├── predictor.py
├── pass_predictor.py
│
├── mount.py
├── guider.py
├── camera.py
│
├── gui/
│   ├── main_window.py
│   ├── sky_view.py
│   └── controls.py
│
├── util/
│
└── main.py
```

---

# 開発ロードマップ

- [x] TLE取得
- [x] ISS位置計算
- [x] Predictor
- [ ] PassPredictor
- [ ] ASCOM接続
- [ ] ASCOM機能確認
- [ ] GoTo制御
- [ ] PulseGuide制御
- [ ] GUI
- [ ] ISSリアルタイム追尾
- [ ] OpenCV画像認識
- [ ] 閉ループ自動追尾