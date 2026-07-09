"""
座標単位変換ユーティリティ

赤経・赤緯の単位変換（時間 ↔ 度）と正規化を提供
"""


class CoordinateConverter:
    """座標系・単位変換"""
    
    HOURS_TO_DEGREES = 15.0   # 1時間 = 15度
    DEGREES_TO_HOURS = 1.0 / 15.0  # 1度 = 1/15時間
    
    @staticmethod
    def ra_hours_to_degrees(ra_hours: float) -> float:
        """
        赤経を時間から度に変換
        
        Args:
            ra_hours: 赤経（時間、0-24）
            
        Returns:
            float: 赤経（度、0-360）
        """
        return ra_hours * CoordinateConverter.HOURS_TO_DEGREES
    
    @staticmethod
    def ra_degrees_to_hours(ra_degrees: float) -> float:
        """
        赤経を度から時間に変換
        
        Args:
            ra_degrees: 赤経（度、0-360）
            
        Returns:
            float: 赤経（時間、0-24）
        """
        return ra_degrees * CoordinateConverter.DEGREES_TO_HOURS
    
    @staticmethod
    def normalize_ra_hours(ra_hours: float) -> float:
        """
        赤経を0-24時間の範囲に正規化
        
        Args:
            ra_hours: 赤経（時間、任意の値）
            
        Returns:
            float: 正規化された赤経（0-24）
        """
        return ra_hours % 24.0
    
    @staticmethod
    def normalize_ra_degrees(ra_degrees: float) -> float:
        """
        赤経を0-360度の範囲に正規化
        
        Args:
            ra_degrees: 赤経（度、任意の値）
            
        Returns:
            float: 正規化された赤経（0-360）
        """
        return ra_degrees % 360.0
    
    @staticmethod
    def normalize_dec_degrees(dec_degrees: float) -> float:
        """
        赤緯を-90-90度の範囲に正規化
        
        Args:
            dec_degrees: 赤緯（度、任意の値）
            
        Returns:
            float: 正規化された赤緯（-90 - +90）
        """
        # 範囲外は上下限に丸める（360度周期の正規化ではない）
        if dec_degrees > 90.0:
            return 90.0
        if dec_degrees < -90.0:
            return -90.0
        return dec_degrees
