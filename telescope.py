"""互換レイヤー: 旧 `telescope.py` 名を維持。"""

from core.ascom.telescope import ASCOMTelescope as Telescope

__all__ = ["Telescope"]