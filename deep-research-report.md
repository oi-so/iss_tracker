# E-ZEUS II の ASCOM 制御と Python 連携

**エグゼクティブサマリ:** E-ZEUS II は汎用赤道儀自動導入装置で、ユーザ開発による ASCOM Telescope ドライバが公開されている。最新の ASCOM ドライバ (Ver.3.00/3.01) をインストールすれば、StellaNavigator、TheSky などの天文ソフトウェアから制御できる。Python からは `win32com.client` や `pythonnet` を使って ASCOM COM インターフェースを呼び出し、`Connected` や `SlewToCoordinates` などのメソッドで制御できる。ISS 追尾では、CelesTrak などから TLE を取得し PyEphem/Skyfield で位置計算した結果を ASCOM 経由で赤道儀に逐次送信する方法が知られている。以下、本件に関する入手先・インストール手順、提供コマンド一覧、Python 例、ISS 追尾ワークフロー、自作パネル事例 (未確認事項含む)、コマンド表、トラブル対策、実験手順・サンプルコードを順にまとめる。  

## 1. ASCOMドライバの有無・入手先・インストール手順・対応インターフェース  

- **ASCOMドライバの存在:** E-ZEUS/E-ZEUS II 用の ASCOM Telescope ドライバが開発され、公開されている。開発者は「星羊翁」氏（星見庵）で、ASCOM Platform のローカルサーバ型ドライバとして提供される。Ver.3.00 (2024年4月29日公開) では E-ZEUS/E-ZEUS II 両対応を謳い、Ver.3.01 (2025年11月16日) に更新されている。更新履歴には、南半球での子午線越え問題や反転動作バグ対応、シミュレータ選択不具合修正などが示されている。ただし2025年時点で E-ZEUS II 実機での動作確認は完了しておらず、問題報告を求めている。  

- **入手先:** 公開先は星見庵サイト等で、リンクは例えば SB工房ブログに掲載されている（「ASCOM Telescope Driver for E-ZEUS」）。AstroArts 屋上ch でも「E-ZEUSII用 ASCOMドライバ (Ver.3.00)」が紹介されている。なおFC2など個人サイトからの公開なので、ウイルスチェック等注意。  

- **インストール手順:** Windows PC に **ASCOM Platform (推奨6.3以上)** と **.NET Framework 4.7.2 以降** をインストールする（AstroArts記事では .NET 4.7.2、ASCOM 6.2 を要求）。次に配布されたインストーラを実行し、ドライバを登録する。ドライバ設定画面でシリアル（USB）ポート番号を設定できる。E-ZEUS II はUSB接続にも対応し、シリアル変換チップ (FTDI など) 経由でWindowsにCOMポートとして認識される。スターカトラスなど外部GPSはASCOM経由で接続可能（内蔵GPSも可、StellaShot3 設定画面）。  

- **対応インターフェース:** このドライバは **ASCOM Telescope インターフェース** に準拠したものであり、Mount（赤道儀）として動作する。Mount 固有のインターフェースはなく、一般的な望遠鏡ドライバとして扱う。対応する機能（追尾、スリュー、シンク、パルスガイド等）は ASCOM Telescope 規格に準じる。  

## 2. ASCOMドライバの提供コマンド（メソッド）の概要  

E-ZEUS II ASCOM ドライバは標準の **ASCOM Telescope** インターフェースを実装する。その主なプロパティ・メソッド例と動作は以下の通り（名称はドライバ実装により多少異なる可能性あり）:  

- **プロパティ:**  
  - `Connected` (Boolean): 接続/切断。`True` で赤道儀に接続。  
  - `RightAscension`, `Declination` (Double): 現在の赤経 (時間単位)・赤緯 (度) 値。  
  - `Azimuth`, `Altitude` (Double): 現在方位・高度 (度)。  
  - `Tracking` (Boolean): 追尾の ON/OFF。  
  - `TrackingRate` (Double): 現在の追尾速度 (Sidereal=1.0 等)。
  - `SideOfPier`, `AtPark` (Enum/Boolean): 子午線越え方向、パーク位置状態。  
  - `CanSlew`, `CanSync`, `CanMoveAxis`, `CanPulseGuide` など: 各機能の可否。  

- **メソッド:**  
  - `SlewToCoordinates(ra, dec)`: 指定赤経・赤緯に向けて動作（同期や移動）。例: `tel.SlewToCoordinates(12.34, 86.7)`。  
  - `SlewToAltAz(alt, az)`: 指定高度・方位に向けて動作。  
  - `SyncToCoordinates(ra, dec)`: 現在向いている位置を指定赤道座標として同期。  
  - `SlewToTarget(ra, dec, equinox)`: 通常は上記と同等の導入。  
  - `AbortSlew()`: 現在の動作 (スリュー/パルス) を即時停止。  
  - `MoveAxis(axis, rate)`: 赤経/赤緯軸を一定速度で動かす (手動微動)。`axis` は通常0=RA, 1=Dec。  
  - `PulseGuide(axis, duration_ms)`: ガイド補正パルス (LX200 Mg コマンドに対応)。`axis` はRA/Dec、`duration_ms` がミリ秒。  
  - `FindHome()`: ホーム (原点) を探索 (対応ドライバによる)。  
  - `Park()`, `Unpark()`: パーク位置への自動導入/解除。  
  - **ガイドレート/追尾レート設定:** 例えば `GuideRate(ra_rate, dec_rate)` や `TrackingRate = value` (サイレードリアル以外の追尾) が利用できる場合もある。  
  - その他、子午線越え制御 (`PierSide` 取得/設定) やステッピングパルス数取得などドライバ依存の拡張機能がある可能性がある。  
  - **例外:** 接続未設定時や不正値で例外が発生する。ASCOMインターフェースが標準で `ASCOM.NotConnectedException` などを投げる。  

これらはすべて一般的なASCOM Telescopeの機能であり、多くのASCOM対応ソフトウェアから同様に呼び出せる。なお、星見庵日記によれば「Southern hemisphereでは子午線越え動作に制限あり」「バックラッシュ補正やサイド固定機能」など特殊機能がVer.3.01で追加されていることも記録されている。  

## 3. Python から ASCOM を呼び出す方法とサンプルコード  

Python から ASCOM デバイスを操作するには、Windows の COM インターフェース経由で ASCOM.DriverAccess ライブラリを使用する方法が一般的である。以下のいずれかの手段がある：  

- **win32com (pywin32)** を使う方法:  
  ```python
  import win32com.client
  # ASCOM Chooser で望遠鏡ドライバを選択
  chooser = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
  chooser.DeviceType = "Telescope"
  driverID = chooser.Choose(None)       # ドライバIDを取得
  telescope = win32com.client.Dispatch(driverID)
  telescope.Connected = True           # 接続開始
  telescope.Tracking = True            # 追尾ON
  telescope.SlewToCoordinates(10.0, 40.0)  # 赤経10h, 赤緯40°にスリュー
  telescope.Connected = False          # 接続終了
  ```
  - この例では星羊翁氏のドライバをChooserで選択する。RASCOM ドライバID（例 `"ASCOM.DriverAccess.Telescope"` はシミュレータ用）ではなく、Chooser で一覧から選ぶのが安全。  
  - `tel.Tracking = True` により恒星時追尾を開始し、`SlewToCoordinates` で導入動作を行う。その他、`telescope.PulseGuide(0, 100)` などでガイドパルスを送ることもできる。  

- **comtypes** を使う方法:  
  ```python
  import comtypes.client
  telescope = comtypes.client.CreateObject("ASCOM.Utilities.Chooser")
  telescope.DeviceType = "Telescope"
  driverID = telescope.Choose(None)
  mount = comtypes.client.CreateObject(driverID)
  mount.Connected = True
  # 以下は同様
  ```
  - `comtypes.client.CreateObject` で同様のオブジェクトを生成できる（win32com と内部動作は似ている）。  

- **pythonnet (clr) + ASCOM.DriverAccess.dll** を使う方法:  
  ```python
  import clr
  clr.AddReference("ASCOM.DriverAccess.dll")
  from ASCOM.DriverAccess import Telescope
  telescope = Telescope("ASCOM.DriverAccess.Telescope")  # または実際のドライバID
  telescope.Connected = True
  telescope.SlewToCoordinates(11.11, 11.11)
  telescope.Tracking = True
  telescope.Connected = False
  ```  
  - IronPython など .NET 対応 Python からは、ASCOM.DriverAccess.dll を読み込めば同等の API が利用できる。  

いずれの方法でも、ASCOM Platform の COM サーバーが介在する。PyEphem/skyfield 等で得た位置を元に、上記 API で赤道儀を動かす。例えば RkBlog の例では、Celestron SkyWatcher ドライバに接続して `SlewToCoordinates` を実行している。

## 4. ISS 追尾の実装例  

**ワークフロー:** ISS など人工衛星の追尾では次の手順を踏む。  
1. **TLEデータ取得:** CelesTrak などから ISS の最新 TLE（2行軌道要素）を取得する。  
2. **軌道計算:** PyEphem や Skyfield を用いて現在時刻における ISS の赤経・赤緯を計算する。Skyfield はSGP4アルゴリズムで精度良く予測できる。  
3. **ASCOM 制御:** 計算結果に従い、一定間隔で赤経・赤緯を ASCOM 経由で望遠鏡に送る。ISS_tracker 例では、PyEphem で予測経路を算出し、その値を元に `SlewToCoordinates` や `MoveAxis` を呼び出して追尾している。  

**実装例:** erellaz 氏の Python スクリプト（ISS_tracker）が参考になる。依存関係は「ASCOM Platform 6.3」「ASCOM Mount ドライバ」「Python module: ephem」などで、`win32com.client`, `ephem`, `datetime`, `urllib2` などを使用している。処理内容は(1) `ephem.readtle` で ISS を定義し、`iss.compute(time)` で現在の天球位置を計算、(2) `telescope.SlewToCoordinates(iss.ra, iss.dec)` で導入する、をループするもの。  ISS追尾の概念フロー（TLE取得→軌道計算→ASCOMで導入、これを繰り返す）を以下に示す。  

```mermaid
flowchart TD
    A[TLE 取得 (CelesTrak など)] --> B[PyEphem/Skyfield で軌道予測]
    B --> C[RA/Dec 計算 (現在時刻)]
    C --> D[Python で ASCOM ドライバ経由制御]
    D --> E[望遠鏡 (赤道儀) 動作]
    E --> C  %% (繰り返し制御)
```  

実装例の簡単なスニペット（イメージ）を示す：  
```python
import ephem, win32com.client, datetime
# ISS TLE（例。最新データを使用）
iss = ephem.readtle("ISS",
    "1 25544U 98067A ...", 
    "2 25544 51.6 ...")
# ASCOMドライバ選択
chooser = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
chooser.DeviceType = "Telescope"
driver = chooser.Choose(None)
telescope = win32com.client.Dispatch(driver)
telescope.Connected = True

# 現在時刻で計算・導入
iss.compute(datetime.datetime.utcnow())
ra = float(iss.ra) * 180.0/3.14159  # PyEphemはラジアンを返す
dec = float(iss.dec) * 180.0/3.14159
telescope.SlewToCoordinates(ra/15.0, dec)  # RAは時間単位に変換
telescope.Connected = False
```
このように、Python で軌道計算結果をASCOMメソッドに渡して追尾する。  

## 5. 自作操作盤・GUI・リモートパネルの事例  

公開情報では、E-ZEUS II 特有の自作操作盤や GUI の事例は見当たらなかった（未確認）。E-ZEUS II はコントローラ内蔵で、付属の **ハンドボックス** により手動追尾・各種設定が可能。ASCOM 経由のカスタムGUIを作る場合は、上記 Python 例のように PC 上でボタンを作り、`MoveAxis` や `SlewToCoordinates` を呼ぶ形になるだろう。部品構成例は明示情報がないが、USBケーブルと各種ボタン・表示器、マイクロコントローラ（例: Arduino）で PC と通信して操作するのが一般的である。回路図・部品リストは未公開。現時点では、ユーザによる独自コントローラ製作の公開例は未確認である。なお Biglobe 取扱説明書によれば、E-ZEUS II はRS-232/USB 接続を備え、ハンドボックス用とオートガイダ用のコネクタがある。  

## 6. コマンド候補一覧

下表は、E-ZEUS II を含む ASCOM Telescope ドライバで一般に使用する代表的コマンド（メソッド）の例である。列は「コマンド名/ASCOMメソッド/引数/期待動作/出典・備考」を示す。実際の動作例がある場合は参考文献を示す。  

| コマンド名・操作           | ASCOM メソッド/プロパティ       | 引数・設定例                  | 期待動作・効果                             | 出典・実例                       |
|---------------------------|--------------------------------|-----------------------------|---------------------------------------|-------------------------------|
| 接続開始／切断            | `Connected` (プロパティ)       | `True` / `False`           | 赤道儀との接続を開始/解除                      | ASCOM標準                         |
| 追尾設定                  | `Tracking` (プロパティ)        | `True` / `False`           | 追尾ON/OFF (恒星時追尾)                     | ASCOM標準         |
| 赤経/赤緯導入 (Slew)       | `SlewToCoordinates(ra, dec)`   | RA (h), Dec (deg)          | 指定赤経/赤緯に望遠鏡を動かす                | ASCOM標準         |
| 高度/方位導入 (Slew)      | `SlewToAltAz(alt, az)`         | Alt, Az (deg)              | 指定高度/方位へ導入                         | ASCOM標準                         |
| 同期                      | `SyncToCoordinates(ra, dec)`   | RA (h), Dec (deg)          | 現在向いている方向を指定座標に同期             | ASCOM標準                         |
| 微動                      | `MoveAxis(axis, rate)`         | `axis=0/1`, `rate=±数`     | 赤経/赤緯軸を指定速度で動かす（微動）           | ASCOM標準                         |
| パルスガイド              | `PulseGuide(axis, duration)`   | `axis=0/1`, duration(ms)   | ガイドパルス送信 (例: `axis=0, duration=500`) | ASCOM標準            |
| パーク／解除             | `Park()` / `Unpark()`          | なし                       | 駐機位置への導入 / 駐機解除                    | ASCOM標準                         |
| 停止                      | `AbortSlew()`                  | なし                       | 現在の動作 (導入/同期) を即時停止              | ASCOM標準                         |
| 赤経値取得               | `RightAscension` (プロパティ)  | なし                       | 現在の赤経（時間単位）を取得                  | ASCOM標準         |
| 赤緯値取得               | `Declination` (プロパティ)     | なし                       | 現在の赤緯（度）を取得                       | ASCOM標準         |
| 方位値取得               | `Azimuth` (プロパティ)         | なし                       | 現在の方位（度）を取得                       | ASCOM標準                         |
| 高度値取得               | `Altitude` (プロパティ)        | なし                       | 現在の高度（度）を取得                       | ASCOM標準                         |
| 副次速度設定            | `TrackingRate`                 | (例: `Sidereal=1.0`)      | 追尾速度 (恒星時以外) を設定                  | ASCOM標準                         |
| 子午線横断サイド取得     | `SideOfPier` (プロパティ)      | なし                       | 現在の子午線越え側 ("PierEast"/"PierWest") | ASCOM標準                         |

各メソッドは標準 ASCOM Telescope インターフェースに従う。動作例として、RkBlog の Pythonサンプルでは `telescope.Tracking = True` 後に `telescope.SlewToCoordinates(ra, dec)` を呼んでいる。PulseGuide 例では LX200 互換コマンド `Mg` に対応しており Ver.3.01で導入されたとされる。  

## 7. トラブルシューティングと注意点  

- **COMポートと接続:** Windows PC のUSBポートに E-ZEUS II を接続すると COM ポートが割り当てられる。デバイスマネージャで正しいポート番号を確認し、ASCOMドライバ設定画面で一致させる。ほかのアプリケーション（StellaShot 等）が同じポートを開いていると競合するため、同時に開かないよう注意する。  

- **Python のビット数と ASCOM:** ASCOM Platform は 32bit/64bit 両対応だが、COM 呼び出しでは Python のビット数 (32bit Python vs 64bit Python) と ASCOM ドライバのビルド(通常32bit)が一致している必要がある。32bit Python (pywin32) を使うか、両者が互換となるよう構成する。  

- **Windows 環境依存:** ASCOM は Windows 専用。ドライバインストールやCOM設定には管理者権限が必要な場合がある。また.NET や Visual C++ ランタイムなど前提ライブラリが欠如していないか確認する。  

- **接続/切断:** Python で `Connected=True/False` を切り替えると赤道儀との接続が制御される。切断忘れでドライバが COM ポートを保持し続けると、次回接続で「ポート使用中」エラーが発生することがある。必ずスクリプト終了前に `Connected=False` とし、オブジェクトを破棄する（`del telescope` や `telescope = None`）ようにする。  

- **同期と子午線越え:** ASCOM ドライバは通常「北半球前提」で動作することが多い。南半球で使用する場合、Ver.3.01 現在では子午線越えが正常に機能しない制限があると報告されている。観測地設定 (経度/緯度) はASCOM経由でドライバに送る必要があるが、不適切な値だと動作がおかしくなるバグも修正されたため、正確に設定する。  

- **タイミング/同期:** ASCOM メソッドは基本的に同期的だが、ドライバ内部ではシリアル通信による制御を行っており、処理に時間がかかる場合がある。例えば大きく動かすスリュー時は完了まで待つ必要があり、その間に次コマンドを送ると失敗する可能性がある。必要に応じて待機 (例:`while(telescope.Slewing): pass`) を入れるとよい。  

- **バックラッシュ補正・反転:** バックラッシュ値などを ASCOM プロパティで設定しないと、スリュー時に誤差が生じる場合がある。星見庵の更新情報には「バックラッシュ補正」「ミラー反転」などがVer2.20-3.01で追加されたとあり、設定画面やコードでこれらのパラメータがいじれるか確認する（未確認）。  

- **環境依存:** ASCOM プラットフォームやドライバは Windows の地域設定に依存しないはずだが、命令語句や小数点／カンマの形式などで注意が必要。Pythonで国際化された数値を扱うときは`.`を使い、ASCOMが受け取れるフォーマットか検証する。  

## 8. 実験手順（ステップバイステップ）とサンプルコード  

**前提条件:** Windows 10/11 環境。ASCOM Platform 6.x（例: 6.4）と .NET 4.7.2+ がインストール済み。Python 3.x (32bit推奨) と `pywin32` モジュール等を準備する。必要に応じて Pythonnet (`clr`) や `comtypes` もインストール。E-ZEUS II は付属USBケーブル or RS-232C (COM9ピン) でPCに接続し、デバイスマネージャでポート番号を確認。  

**実験手順例:**  
1. ASCOM Platform のインストーラを実行・インストール。`ASCOM Utilities` 中の「ASCOM Chooser」で望遠鏡 (Telescope) ジャンルを確認する。  
2. 星羊翁氏の E-ZEUS II ASCOM ドライバを配布サイトからダウンロード・インストール。インストール後、ASCOM Chooser の Telescope 欄に「E-ZEUS Telescope」等が追加されていることを確認。  
3. PC に E-ZEUS II を接続し、ASCOM ドライバ設定でポート番号や通信速度 (9600bps/8N1 推奨) などを設定。E-ZEUS II は標準では RS-232C (D-Sub9) 接続で USB変換基板付き、2400～9600bps など複数設定可能な場合が多い。  
4. StellaShot3 や StellaNavigator 等でドライバに接続し、簡単な導入 (シンク) ができるかテストする。これで動作確認が取れたら Python 連携に進む。  
5. Python 環境で `pywin32` をインストール (`pip install pywin32`)。  
6. 簡単な Python コードを書き、ASCOM ドライバに接続してみる。下記にサンプルコードを示す。  

```python
import win32com.client

# ASCOM Chooser でドライバを選択
chooser = win32com.client.Dispatch("ASCOM.Utilities.Chooser")
chooser.DeviceType = "Telescope"
driverID = chooser.Choose(None)  # 例: "ASCOM.YourEZeus.Telescope"
# 実際のドライバIDを選択後
telescope = win32com.client.Dispatch(driverID)

# 接続と動作例
telescope.Connected = True
print("接続状態:", telescope.Connected)
print("現在のRA/Dec:", telescope.RightAscension, telescope.Declination)

# 任意の座標 (例: RA=5h, Dec=30°) へ導入
telescope.SlewToCoordinates(5.0*15.0, 30.0)  # RAは度に換算(5h=75°)
# または微動: telescope.MoveAxis(0, 1.0)  # RA軸を正方向に微速運転

telescope.Connected = False
```
- このコードではまず Chooser で E-ZEUSドライバを選択し、`Connected=True` で接続する。`SlewToCoordinates` で赤経5h・赤緯30°に導入する例を示した。  
- 成功すれば望遠鏡が動き、時間経過後に指定位置に導入される。`RightAscension` 等で現在位置を読み出せることも確認する。  

**検証:** 上記コードで望遠鏡が動くこと、`Connected` プロパティが正しく切り替わることを確認する。エラーが出たら COM ポート設定、ドライバ選択、ASCOM Platform のバージョンを見直す。  

## 9. 出典一覧と信頼度評価  

- アストロアーツ屋上ch「E-ZEUSIIをステラシリーズで使おう」 – AstroArts社公式ブログ記事。E-ZEUS II用ASCOMドライバのインストール手順・環境などを解説。**信頼度: 高**。  
- SB工房ブログ（tentai.asablo.jp）「大型用E-ZEUSⅡのご紹介」 – メーカー（SB工房）ブログ記事。ASCOMドライバの存在と使用例を記載。**信頼度: 高**。  
- 星見庵日記（blog.fc2）「E-ZEUS ASCOM Driver 更新（Ver.3.01）」 – ドライバ開発者による更新ログ。最新修正点やE-ZEUS IIの動作状況を報告。**信頼度: 中**。  
- RkBlog (rkblog.dev) 「ASCOM for end user application developers」 – PythonによるASCOM制御例。ASCOM.DriverAccessを使った接続・導入サンプルあり。**信頼度: 中**。  
- GitHub: erellaz/ISS_tracker – PythonでASCOMを使ったISS追尾プログラム。README に環境・依存モジュールと概要、コードあり。**信頼度: 中**。  
- erellaz.com「ISS tracking」 – 上記プログラムの紹介記事。ASCOMとPyEphemによる追尾手法を解説。**信頼度: 中**。  
- Skyfield Documentation (rhodesmill.org) – Skyfield の衛星位置計算解説。TLE取得とSGP4予測について言及。**信頼度: 高**（公式ドキュメント）。  
- E-ZEUS取扱説明書 (biglobe.ne.jp) – E-ZEUSハード仕様（RS232C/USB接続、ハンドボックス等）。**信頼度: 中**（旧版取説）。  

以上の情報を基に検討したが、不明点や未確認事項には「未確認」と記述した。特に E-ZEUS II の ASCOM ドライバ動作状況や自作パネル事例は限られた情報であるため、実機検証や追加の情報提供が望ましい。