"""출처 접속 확인(한 번씩). 이번: 새로 고른 사진 6장 주소가 열리는지 확인 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon)"}
def get(u, raw=False):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        b = r.read(); return b if raw else json.loads(b)
API = "https://commons.wikimedia.org/w/api.php?"
Q = {}
out = {"cands": {}, "check": {}}
for k, q in Q.items():
    try:
        s = get(API + urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": 8, "format": "json"}))
        titles = [h["title"] for h in s["query"]["search"] if h["title"].lower().endswith((".jpg", ".jpeg", ".png"))][:6]
        res = []
        if titles:
            ii = get(API + urllib.parse.urlencode({"action": "query", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiextmetadatafilter": "LicenseShortName|Artist|ImageDescription|DateTimeOriginal", "iiurlwidth": 500, "titles": "|".join(titles), "format": "json"}))
            for pg in ii["query"]["pages"].values():
                i = pg["imageinfo"][0]; md = i.get("extmetadata", {})
                item = {"t": pg["title"], "w": i["width"], "h": i["height"], "lic": md.get("LicenseShortName", {}).get("value"), "by": md.get("Artist", {}).get("value", "")[:200], "desc": md.get("ImageDescription", {}).get("value", "")[:300], "date": md.get("DateTimeOriginal", {}).get("value", "")[:40], "thumb": i["thumburl"].split("?")[0]}
                try:
                    item["b64"] = base64.b64encode(get(item["thumb"], True)).decode(); time.sleep(1.5)
                except Exception as e:  # noqa: BLE001
                    item["err"] = str(e)[:100]
                res.append(item)
        out["cands"][k] = res
    except Exception as e:  # noqa: BLE001
        out["cands"][k] = {"err": f"{type(e).__name__}: {str(e)[:150]}"}
    time.sleep(2)
for u in ["https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg/1280px-Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg/960px-Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg/1920px-Donald_Trump_state_visit_to_the_United_Arab_Emirates%2C_2025-05-15_P20250515DT-1523.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg/1280px-Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg/960px-Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg/1920px-Keir_Starmer%2C_Donald_Trump%2C_signing_tech_deal%2C_smiling%2C_UK_state_visit%2C_2025_%28cropped%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/P20220909AS-1281_%2852517058506%29.jpg/1280px-P20220909AS-1281_%2852517058506%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/P20220909AS-1281_%2852517058506%29.jpg/960px-P20220909AS-1281_%2852517058506%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b4/P20220909AS-1281_%2852517058506%29.jpg/1920px-P20220909AS-1281_%2852517058506%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg/1280px-NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg/960px-NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/f/fe/NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg/1920px-NASA%27s_CLPS_Firefly_Blue_Ghost_Mission_1_Launch_%28KSC-20250115-PH-FMX01_0004%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg/1280px-Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg/960px-Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/3/32/Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg/1920px-Donald_Trump_announces_the_Golden_Dome_missile_defense_system_inside_the_White_House_Oval_Office_on_May_20%2C_2025.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg/1280px-Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg/960px-Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg", "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0e/Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg/1920px-Vandenberg_Launches_the_SDA_T1TL-C_%289368625%29.jpg"]:
    try:
        b = get(u, True); out["check"][u] = {"ok": True, "n": len(b), "b64": base64.b64encode(b).decode() if "960px" in u else ""}
    except Exception as e:  # noqa: BLE001
        out["check"][u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}
    time.sleep(2)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
