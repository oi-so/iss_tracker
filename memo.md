# ISS Tracker 開発メモ

最終更新: 2026-07-09

---

# プロジェクト概要

SkyfieldでISSの軌道を計算し、ASCOM経由でE-ZEUS II赤道儀を制御してISSを自動追尾するソフトウェア。

最終目標:


TLE
↓
Skyfield
↓
ISS位置計算
↓
ASCOM
↓
E-ZEUS II
↓
赤道儀
↓
Sony α7III


さらに将来的には画像認識による閉ループ制御を行う。


Skyfield予測
↓
赤道儀制御
↓
カメラ撮影
↓
OpenCVでISS検出
↓
位置誤差計算
↓
PulseGuide補正


---

# 現在の進捗

## 完了

- TLE取得
- SkyfieldによるISS位置計算
- 観測地点補正
- 現在位置計算
- 指定時刻での位置計算
- 未来位置計算
- リアルタイム追尾ループ
- MountSimulator作成
- PulseGuide制御シミュレーション
- P制御による追尾補正
- ASCOM Platform導入
- E-ZEUS Telescope Driver確認
- ASCOM ChooserでEZEUS Telescope選択確認

---

## 未実装

- ASCOM実機接続テスト
- 赤道儀現在位置取得
- GoTo完了待機
- ISS導入処理
- 実機PulseGuide制御
- GUI
- PassPredictor
- OpenCVによるISS検出
- 閉ループ制御

---

# 現在のフォルダ構成


iss_tracker/

├── config.py
├── models.py
├── tle.py
├── orbit.py
├── predictor.py
├── tracker.py
├── guider.py
├── mount_simulator.py
├── telescope.py
└── main.py


---

# システム構成


TLELoader

↓

EarthSatellite

↓

OrbitCalculator

↓

ISSPosition

↓

Tracker

↓

Guider

↓

Mount

↓

ASCOM / E-ZEUS II


---

# 各クラス

---

# TLELoader

## 役割

ISSの最新TLEを取得する。

使用例:

```python
tle = TLELoader()

tle.update()

satellite = tle.satellite
OrbitCalculator
役割

Skyfieldを用いてISS位置を計算する。

保持する情報:

time

RA

Dec

distance

altitude

azimuth
メソッド
get_position()

現在時刻のISS位置を取得。

position = orbit.get_position()
get_position_after()

指定時間後のISS位置を取得。

future = orbit.get_position_after(
    base_time,
    10
)

例:

base_time + 10秒

後のISS位置を返す。

get_position_at()

指定したSkyfield Timeの位置を取得。

position = orbit.get_position_at(time)
Predictor
役割

未来のISS位置列を生成する。

例:

predictor.predict(
    duration=300,
    interval=0.05
)

生成:

0秒後

0.05秒後

0.10秒後

...

300秒後
Tracker
役割

ISS追尾制御。

現在の処理:

実時間取得

↓

ISS位置計算

↓

赤道儀位置取得

↓

誤差計算

↓

Guiderへ渡す

↓

PulseGuide

↓

赤道儀更新

現在の制御:

while True:

    elapsed = time.perf_counter()

    position = orbit.get_position_after(
        base_time,
        elapsed
    )

    mount_position = mount.get_position()

    error計算

    guider.guide()

Guider
役割

位置誤差を速度指令へ変換する。

現在:

P制御

速度 = 誤差 × Kp

例:

ra_rate = ra_error * kp

dec_rate = dec_error * kp

将来追加:

PID制御
最大速度制限
加速度制限
摩擦補正
MountSimulator
役割

赤道儀制御テスト用。

実装済み:

goto()

pulse_guide()

get_position()

update()

現在:

目標位置

↓

速度制限

↓

現在位置更新

を再現。

Telescope
役割

ASCOM経由でE-ZEUS IIを制御する。

現在:

ASCOM Chooser

↓

EZEUS Telescope

↓

Connected=True

まで確認。

connect()

ASCOM接続。

chooser = win32com.client.Dispatch(
    "ASCOM.Utilities.Chooser"
)

chooser.DeviceType = "Telescope"

progid = chooser.Choose(None)

scope = win32com.client.Dispatch(
    progid
)

scope.Connected = True
goto()

GoTo制御。

予定:

scope.SlewToCoordinatesAsync(
    ra.hours,
    dec.degrees
)
今後追加
get_position()

赤道儀現在位置取得。

予定:

ra = scope.RightAscension

dec = scope.Declination
wait_slew()

GoTo完了待機。

予定:

while scope.Slewing:

    time.sleep(0.1)
pulse_guide()

ASCOM PulseGuide。

実機での運用予定

現在のSUPER STAR IVを利用した流れ:

赤道儀起動

↓

SUPER STAR IV接続

↓

位置合わせ

↓

ASCOM接続

↓

ISS位置計算

↓

ISS未来位置へGoTo

↓

GoTo完了待機

↓

PulseGuide追尾開始
アライメントについて

アライメントはSUPER STAR IV側で行う。

目的:

モーター角度

↓

赤経赤緯座標


の対応付け。

Python側でアライメント処理は行わない。

GoToについて

ISSは移動速度が速いため、

現在位置ではなく未来位置へ導入する。

例:

現在

20:00:00

ISS:

RA 120°
Dec 20°


GoTo時間

20秒


↓

20:00:20のISS位置へGoTo
追尾制御
導入
ISS未来位置計算

↓

GoTo

↓

完了待機
追尾
ISS予測位置

↓

現在赤道儀位置

↓

差分計算

↓

PulseGuide

ASCOM

使用:

ASCOM Platform

↓

EZEUS Telescope Driver

↓

Python(pywin32)


ASCOM Chooser設定:

EZEUS Telescope
現在確認できたこと
シミュレーション

確認済み:

ISS位置変化
時刻同期
Mount移動
PulseGuide補正
P制御
現在の問題

初期位置からISSまでの導入処理が必要。

理由:

PulseGuideは微小補正用。

大きな移動:

GoTo

小さい補正:

PulseGuide

で分ける必要がある。

次の実装優先順位
1. Telescope現在位置取得

追加:

get_position()

目的:

赤道儀が現在向いている場所を取得。

2. GoTo完了待機

追加:

wait_slew()

目的:

ISS導入完了確認。

3. Acquire処理

追加:

ISS未来位置計算

↓

GoTo

↓

完了待機
4. 実機PulseGuide

ASCOM:

PulseGuide()

を使用。

5. 画像認識

将来:

Sony α7III

↓

画像取得

↓

OpenCV

↓

ISS検出

↓

補正量計算

↓

PulseGuide
最終アーキテクチャ
                TLE
                 |
                 v
          OrbitCalculator
                 |
                 v
              Tracker
             /       \
            /         \
       Guider       Telescope
                       |
                       v
                    ASCOM
                       |
                       v
                  E-ZEUS II
                       |
                       v
                    赤道儀
開発方針
シミュレータで制御確認
ASCOMは抽象化する
GoToとPulseGuideを分離
SUPER STAR IVでアライメント
Pythonは追尾制御のみ担当
将来的には画像認識による閉ループ制御を実装する