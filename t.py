import win32com.client
from time import sleep

progid = "ASCOM.EZEUS.Telescope" 
print("Connecting to:", progid)
scope = win32com.client.Dispatch(progid)

# 接続
scope.Connected = True

# --- アライメント（Sync）処理 ---
print("--- Alignment Start ---")

# 1. ターゲットとなる座標（時・分・秒、度・分・秒から変換した値）を指定
# ※ASCOMでは時（Hour）や度（Degree）を10進数の浮動小数点（float）で渡す必要があります。

# 赤経（RA）: 10h 11m 45.1s  => 10 + 11/60 + 45.1/3600
target_ra = 10.0 + (11.0 / 60.0) + (45.1 / 3600.0)

# 赤緯（Dec）: +12° 40' 20.7" => 12 + 40/60 + 20.7/3600
target_dec = 12.0 + (40.0 / 60.0) + (20.7 / 3600.0)

print(f"Target RA (Decimal Hours): {target_ra}")
print(f"Target Dec (Decimal Degrees): {target_dec}")

scope.TargetRightAscension = target_ra
scope.TargetDeclination = target_dec
scope.SyncToTarget()

# TODO: できなかったらこれを使う
# scope.SyncToCoordinates(target_ra, target_dec)

print("Sync Completed!")

# --- 確認 ---
print("Current RA =", scope.RightAscension)
print("Current Dec =", scope.Declination)

sleep(2)

# 切断
scope.Connected = False
print("Disconnected successfully.")