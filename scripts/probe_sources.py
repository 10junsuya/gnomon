"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 사진 주소가 실제로 열리는지 확인하고, 화면 점검용으로 잠깐 받아 둬요 (대표 요청 2026-11-22). 결과 → data/probe.json, 사진은 base64로 probe.json에 잠깐 (다음 확인 때 덮어씀)"""
import base64, json, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; image check)"}
U = [
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/06/JASM_Kumamoto_2024_03.jpg/960px-JASM_Kumamoto_2024_03.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0b/Intel_Ohio_One_%282024-02-11-04-16-53_UMBRA-06%29.tiff/lossy-page1-960px-Intel_Ohio_One_%282024-02-11-04-16-53_UMBRA-06%29.tiff.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0c/Google_Data_Center%2C_Council_Bluffs_Iowa_%2849062863796%29.jpg/960px-Google_Data_Center%2C_Council_Bluffs_Iowa_%2849062863796%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/26/Overview_of_cooling_towers_of_Dukovany_Nuclear_Power_Station_near_Dukovany%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg/960px-Overview_of_cooling_towers_of_Dukovany_Nuclear_Power_Station_near_Dukovany%2C_T%C5%99eb%C3%AD%C4%8D_District.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2c/Construction_at_Vogtle_Unit_3_-_August_2013_%2814676545094%29.jpg/960px-Construction_at_Vogtle_Unit_3_-_August_2013_%2814676545094%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/50/TSMC_Fab_18_and_fields_May_2025.jpg/960px-TSMC_Fab_18_and_fields_May_2025.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/53/KSLV-II_Nuri_and_the_launchpad_01.jpg/960px-KSLV-II_Nuri_and_the_launchpad_01.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/Data_centers_in_Ashburn.jpg/960px-Data_centers_in_Ashburn.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Blue_Ghost_M1_on_the_Moon.png/960px-Blue_Ghost_M1_on_the_Moon.png",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8d/Artemis_II_Launch_%28NHQ202604010307%29.jpg/960px-Artemis_II_Launch_%28NHQ202604010307%29.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/9/94/231105-1_TSMC_Fab_21_construction.jpg/960px-231105-1_TSMC_Fab_21_construction.jpg",
 "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b9/Three_Mile_Island_%28color%29.jpg/960px-Three_Mile_Island_%28color%29.jpg"
]
out = {}
for u in U:
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            b = r.read(); ct = r.headers.get("Content-Type")
        out[u] = {"ok": True, "ct": ct, "bytes": len(b), "b64": base64.b64encode(b).decode()}
    except Exception as e:  # noqa: BLE001
        out[u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:160]}"}
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
