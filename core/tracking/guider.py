"""
ガイド制御（PulseGuide生成）

ISS追尾用のガイド補正速度を計算し、PulseGuideに変換
"""

from abc import ABC, abstractmethod


class Guider(ABC):
    def __init__(self, mount, config=None):
        self.mount = mount
        self.config = config

    @abstractmethod
    def guide(
        self,
        ra_velocity_deg_per_sec: float,
        dec_velocity_deg_per_sec: float,
        ra_error_deg: float,
        dec_error_deg: float,
    ) -> None:
        pass


    @abstractmethod
    def stop(self) -> None:
        """
        ガイド補正停止
        """
        pass
