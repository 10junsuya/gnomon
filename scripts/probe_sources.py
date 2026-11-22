"""출처 접속 확인(한 번씩). 이번: 바꿀 사진 후보를 눈으로 확인하려고 잠깐 받아 둠 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; contact via GitHub issues) python-urllib"}
U = [
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/20/TerraPower_Signing_Ceremony-0124_%2855140163015%29.jpg/1280px-TerraPower_Signing_Ceremony-0124_%2855140163015%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/TerraPower_Signing_Ceremony-0151_%2855140163535%29.jpg/1280px-TerraPower_Signing_Ceremony-0151_%2855140163535%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f7/TerraPower_Signing_Ceremony-0121_%2855140163000%29.jpg/1280px-TerraPower_Signing_Ceremony-0121_%2855140163000%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6c/Three_Mile_Island_Nuclear_Generating_Station_%2851142893665%29.jpg/1280px-Three_Mile_Island_Nuclear_Generating_Station_%2851142893665%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Construction_at_Vogtle_Nuclear_Plant.jpg/1280px-Construction_at_Vogtle_Nuclear_Plant.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/56/Narvikbukta_Kveldssol.JPG/1280px-Narvikbukta_Kveldssol.JPG",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Joe_Biden_at_the_TSMC_Semiconductor_Plant_in_Phoenix_%28P20221206AS-0794%29.jpg/1280px-Joe_Biden_at_the_TSMC_Semiconductor_Plant_in_Phoenix_%28P20221206AS-0794%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/7/74/AP1000_reactors_Virgil_Summer_Nuclear_Generating_Station.jpg/1280px-AP1000_reactors_Virgil_Summer_Nuclear_Generating_Station.jpg"
]
out = {}
for u in U:
    time.sleep(5)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            out[u] = {"ok": True, "b64": base64.b64encode(r.read()).decode()}
    except Exception as e:  # noqa: BLE001
        out[u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
