"""互換レイヤー: 旧 `tle.py` から新構成を使うためのラッパー。"""

from core.astronomy.tle_loader import TLELoader

__all__ = ["TLELoader"]