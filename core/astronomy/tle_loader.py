from pathlib import Path
from typing import Optional

import requests
from skyfield.api import EarthSatellite

from config import DEFAULT_LOCAL_TLE_PATH, TLE_URL


class TLELoader:
    def __init__(self):
        self.satellite = None

    def update(
        self,
        local_path: Optional[str | Path] = None,
        allow_network: bool = False,
        timeout: int = 10,
        force_reload: bool = False,
    ):
        """
        ISSのTLEを読み込む。

        優先順位:
        1) local_path
        2) DEFAULT_LOCAL_TLE_PATH
        3) (allow_network=True の場合) CelesTrak
        """
        candidates = []
        if local_path is not None:
            candidates.append(Path(local_path))
        candidates.append(Path(DEFAULT_LOCAL_TLE_PATH))

        if not force_reload:
            for path in candidates:
                if path.exists():
                    self._load_from_text(path.read_text(encoding="utf-8"))
                    return

        if allow_network or force_reload:
            text = requests.get(TLE_URL, timeout=timeout).text
            print(f"ISS TLEをネットワークから取得しました: {TLE_URL}")
            # ISS TLEを上書き保存
            with open(DEFAULT_LOCAL_TLE_PATH, "w", encoding="utf-8") as f:
                f.write(text)

            self._load_from_text(text)
            return

        raise RuntimeError(
            "ISS TLEを読み込めませんでした。"
            "ローカルファイル(data/iss.tle)を用意するか、allow_network=Trueを指定してください。"
        )

    def _load_from_text(self, text: str):
        lines = [line.strip() for line in text.splitlines() if line.strip()]

        for i, line in enumerate(lines):
            # 名前行に ISS を含む3行セットを探す
            if "ISS" in line.upper() and i + 2 < len(lines):
                tle1 = lines[i + 1]
                tle2 = lines[i + 2]

                if tle1.startswith("1 ") and tle2.startswith("2 "):
                    self.satellite = EarthSatellite(tle1, tle2, lines[i])
                    return

        # CelesTrak形式のように名前行がない場合を考慮
        for i in range(len(lines) - 1):
            if lines[i].startswith("1 ") and lines[i + 1].startswith("2 "):
                self.satellite = EarthSatellite(lines[i], lines[i + 1], "ISS")
                return

        raise RuntimeError("ISS TLEが見つかりません")
