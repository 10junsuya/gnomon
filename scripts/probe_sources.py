"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 화면 사진(위키미디어 공용) 라이선스·주소 확인 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import json, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; photo license check)"}
T = ["File:Artemis II Launch (NHQ202604010307).jpg", "File:Three Mile Island (color).jpg",
     "File:231105-1 TSMC Fab 21 construction.jpg", "File:Data centers in Ashburn.jpg",
     "File:KSLV-II Nuri and the launchpad 01.jpg", "File:Construction at Vogtle Nuclear Plant.jpg",
     "File:Construction at Vogtle Unit 3 - August 2013 (14676545094).jpg", "File:JASM Kumamoto 2024 03.jpg",
     "File:Dukovany.JPG", "File:Overview of cooling towers of Dukovany Nuclear Power Station near Dukovany, Třebíč District.jpg",
     "File:CLPS Firefly Blue Ghost Mission 1 (KSC-20250114-PH-KLS01 0006).jpg", "File:Blue Ghost M1 on the Moon.png",
     "File:Google Data Center, Council Bluffs Iowa (49062863796).jpg", "File:Utah Data Center.jpg",
     "File:TSMC Fab 18 and fields May 2025.jpg", "File:Intel Ohio One (2024-02-11-04-16-53 UMBRA-06).tiff"]
out = {}
for i in range(0, len(T), 8):
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": "1280",
         "titles": "|".join(T[i:i + 8])}
    u = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q)
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
            j = json.loads(r.read())
        for p in j.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {})
            g = lambda k: (m.get(k) or {}).get("value", "")
            out[p.get("title")] = {"thumb": ii.get("thumburl"), "page": ii.get("descriptionurl"), "lic": g("LicenseShortName"),
                                   "artist": g("Artist")[:300], "credit": g("Credit")[:300], "usage": g("UsageTerms"), "attr": g("AttributionRequired")}
    except Exception as e:  # noqa: BLE001
        out[f"err{i}"] = f"{type(e).__name__}: {str(e)[:160]}"
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
