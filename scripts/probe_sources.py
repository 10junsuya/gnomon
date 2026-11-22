"""출처 접속 확인(한 번씩). 이번: 그림이 겹치는 프로젝트의 관련 사진 후보 찾기·현재 사진 열리는지 확인 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon)"}
def get(u, raw=False):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        b = r.read(); return b if raw else json.loads(b)
API = "https://commons.wikimedia.org/w/api.php?"
Q = {
 "golden": "Trump announces Golden Dome missile defense Oval Office",
 "uae": "Trump Abu Dhabi UAE AI campus May 2025",
 "uk": "Trump Starmer Technology Prosperity Deal signing",
 "intel-oh": "Intel Ohio groundbreaking New Albany 2022",
 "sda": "Space Development Agency Tranche 1 launch Falcon 9",
 "iris": "IRIS2 satellite constellation ESA",
 "de-space": "Weltraumkommando Bundeswehr",
 "skh-in": "Purdue Research Park West Lafayette",
 "arg": "Patagonia Neuquen data center OpenAI Stargate Argentina",
 "sgkr": "Sam Altman Lee Jae-myung",
}
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
for u in ["https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/FTG-15_Flight_Test_%284108842%29.jpeg/1280px-FTG-15_Flight_Test_%284108842%29.jpeg",
          "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Blue_Ghost_M1_on_the_Moon.png/1280px-Blue_Ghost_M1_on_the_Moon.png",
          "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/Blue_Ghost_M1_on_the_Moon.png/960px-Blue_Ghost_M1_on_the_Moon.png"]:
    try:
        b = get(u, True); out["check"][u] = {"ok": True, "n": len(b), "b64": base64.b64encode(b).decode() if "960px" in u else ""}
    except Exception as e:  # noqa: BLE001
        out["check"][u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}
    time.sleep(2)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
