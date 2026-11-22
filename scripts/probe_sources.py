"""출처 접속 확인(한 번씩). 이번: 달 착륙선·UAE·영국·노르웨이 관련 사진 후보 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon)"}
def get(u, raw=False):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
        b = r.read(); return b if raw else json.loads(b)
API = "https://commons.wikimedia.org/w/api.php?"
Q = {
 "clps1": "Blue Ghost Mission 1 lander Firefly Kennedy",
 "clps2": "Odysseus lander Intuitive Machines Moon surface",
 "clps3": "Commercial Lunar Payload Services lander",
 "uae": "Trump Abu Dhabi May 2025 Mohamed bin Zayed",
 "uk": "Trump Starmer Chequers September 2025",
 "nor": "Narvik Norway hydropower",
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
for u in []:
    try:
        b = get(u, True); out["check"][u] = {"ok": True, "n": len(b), "b64": base64.b64encode(b).decode() if "960px" in u else ""}
    except Exception as e:  # noqa: BLE001
        out["check"][u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}
    time.sleep(2)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
