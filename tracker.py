"""互換レイヤー: 旧 `tracker.py` 名を維持。"""

from core.tracking.tracker import ISSTracker as Tracker

__all__ = ["Tracker"]