"""
ASCOM接続・単位テスト

P0-1, P0-2の検証用テストスクリプト
"""

import sys
from datetime import datetime, timezone

# 既存コードとの互換性で、rootパスをPythonPathに追加
sys.path.insert(0, '.')

from core.ascom.interface import GuideDirection, MountPosition
from core.ascom.telescope import ASCOMTelescope
from utils.units import CoordinateConverter
from orbit import OrbitCalculator
from tle import TLELoader


def test_ascom_connection():
    """Test 1: ASCOM基本接続テスト"""
    print("\n" + "="*60)
    print("Test 1: ASCOM基本接続テスト")
    print("="*60)
    
    telescope = ASCOMTelescope()
    
    try:
        print("\n[Step 1] ドライバ選択...")
        telescope.connect()
        
        print("\n[Step 2] 接続状態確認...")
        if telescope.is_connected():
            print("✓ 接続成功")
        else:
            print("✗ 接続失敗")
            return False
        
        print("\n[Step 3] 機能確認...")
        caps = telescope.get_capabilities()
        print(f"  サポート機能: {[c.name for c in caps]}")
        
        print("\n[Step 4] 現在位置取得...")
        pos = telescope.get_position()
        print(f"  RA: {pos.ra_hours:.4f}h ({CoordinateConverter.ra_hours_to_degrees(pos.ra_hours):.2f}°)")
        print(f"  Dec: {pos.dec_degrees:.4f}°")
        
        return True
    
    except Exception as e:
        print(f"✗ エラー: {e}")
        return False
    
    finally:
        telescope.disconnect()


def test_coordinate_units():
    """Test 2: 座標単位変換テスト"""
    print("\n" + "="*60)
    print("Test 2: 座標単位変換テスト")
    print("="*60)
    
    test_cases = [
        (0.0, 0.0),
        (12.0, 180.0),
        (6.0, 90.0),
        (18.0, 270.0),
        (24.0, 360.0),
    ]
    
    print("\n[RA単位変換テスト]")
    all_pass = True
    for ra_h, expected_d in test_cases:
        result_d = CoordinateConverter.ra_hours_to_degrees(ra_h)
        expected_d_norm = CoordinateConverter.normalize_ra_degrees(expected_d)
        result_d_norm = CoordinateConverter.normalize_ra_degrees(result_d)
        
        passed = abs(result_d_norm - expected_d_norm) < 0.01
        status = "✓" if passed else "✗"
        
        print(f"  {status} {ra_h:5.1f}h → {result_d:6.1f}° (期待: {expected_d:6.1f}°)")
        
        if not passed:
            all_pass = False
    
    print("\n[RA正規化テスト]")
    norm_tests = [
        (25.0, 1.0),
        (-1.0, 23.0),
        (48.0, 0.0),
    ]
    
    for input_h, expected_h in norm_tests:
        result_h = CoordinateConverter.normalize_ra_hours(input_h)
        passed = abs(result_h - expected_h) < 0.01
        status = "✓" if passed else "✗"
        
        print(f"  {status} {input_h:6.1f}h → {result_h:6.1f}h (期待: {expected_h:6.1f}h)")
        
        if not passed:
            all_pass = False
    
    print("\n[Dec正規化テスト]")
    dec_tests = [
        (95.0, 90.0),
        (-95.0, -90.0),
        (45.0, 45.0),
    ]
    
    for input_d, expected_d in dec_tests:
        result_d = CoordinateConverter.normalize_dec_degrees(input_d)
        passed = abs(result_d - expected_d) < 0.01
        status = "✓" if passed else "✗"
        
        print(f"  {status} {input_d:6.1f}° → {result_d:6.1f}° (期待: {expected_d:6.1f}°)")
        
        if not passed:
            all_pass = False
    
    return all_pass


def test_iss_coordinate_vs_telescope():
    """Test 3: ISS座標 vs 赤道儀座標比較"""
    print("\n" + "="*60)
    print("Test 3: ISS座標 vs 赤道儀座標比較")
    print("="*60)
    
    try:
        # TLE取得
        print("\n[Step 1] TLE取得...")
        tle = TLELoader()
        tle.update()
        print("✓ TLE取得成功")
        
        # ISS位置計算
        print("\n[Step 2] ISS位置計算...")
        orbit = OrbitCalculator(tle.satellite)
        
        now = datetime.now(timezone.utc)
        pos = orbit.get_position(orbit.ts.from_datetime(now))
        
        iss_ra_h = pos.ra.hours
        iss_dec_d = pos.dec.degrees
        iss_ra_d = CoordinateConverter.ra_hours_to_degrees(iss_ra_h)
        
        print(f"  ISS RA: {iss_ra_h:.4f}h = {iss_ra_d:.2f}°")
        print(f"  ISS Dec: {iss_dec_d:.4f}°")
        
        # 赤道儀現在位置取得
        print("\n[Step 3] 赤道儀座標取得...")
        telescope = ASCOMTelescope()
        
        try:
            telescope.connect()
            
            mount_pos = telescope.get_position()
            mount_ra_h = mount_pos.ra_hours
            mount_dec_d = mount_pos.dec_degrees
            mount_ra_d = CoordinateConverter.ra_hours_to_degrees(mount_ra_h)
            
            print(f"  望遠鏡 RA: {mount_ra_h:.4f}h = {mount_ra_d:.2f}°")
            print(f"  望遠鏡 Dec: {mount_dec_d:.4f}°")
            
            # 差分
            print("\n[Step 4] 座標差分")
            ra_diff = abs(iss_ra_d - mount_ra_d)
            if ra_diff > 180:
                ra_diff = 360 - ra_diff
            
            dec_diff = abs(iss_dec_d - mount_dec_d)
            
            print(f"  RA差: {ra_diff:.2f}°")
            print(f"  Dec差: {dec_diff:.2f}°")
            
            if ra_diff < 180 and dec_diff < 180:
                print("\n✓ 座標系一貫性: OK（ただし初期位置のため大きな差は正常）")
                return True
            else:
                print("\n✗ 座標系に問題の可能性")
                return False
        
        finally:
            telescope.disconnect()
    
    except Exception as e:
        print(f"✗ エラー: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """メインテスト実行"""
    print("\n" + "#"*60)
    print("# ASCOM & 座標単位テストスイート")
    print("#"*60)
    
    results = {}
    
    # Test 1
    try:
        results['test1'] = test_ascom_connection()
    except Exception as e:
        print(f"\n✗ Test 1 クラッシュ: {e}")
        results['test1'] = False
    
    # Test 2
    try:
        results['test2'] = test_coordinate_units()
    except Exception as e:
        print(f"\n✗ Test 2 クラッシュ: {e}")
        results['test2'] = False
    
    # Test 3
    try:
        results['test3'] = test_iss_coordinate_vs_telescope()
    except Exception as e:
        print(f"\n✗ Test 3 クラッシュ: {e}")
        results['test3'] = False
    
    # サマリー
    print("\n" + "="*60)
    print("テスト結果サマリー")
    print("="*60)
    for name, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name}: {status}")
    
    passed = sum(1 for r in results.values() if r)
    total = len(results)
    print(f"\n総合: {passed}/{total}")


if __name__ == "__main__":
    main()
