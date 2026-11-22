"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 사진 후보의 라이선스·저자·1280px 주소 확인, 화면 점검용으로 잠깐 받아 둠 (대표 요청 2026-11-22). 결과 → data/probe.json (다음 확인 때 덮어씀)"""
import base64, json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; contact via GitHub issues) python-urllib"}
T = [
 "File:231105-1 TSMC Fab 21 construction.jpg", "File:Three Mile Island (color).jpg",
 "File:Frontier supercomputer (52291130197).jpg", "File:Frontier Supercomputer (3).jpg",
 "File:JUPITER racks with logos of supporters and partners. Copyright- Forschungszentrum Jülich - Sascha Kreklau.jpg",
 "File:Gas centrifuge cascade.jpg",
 "File:President Joe Biden announces CHIPS and Science Act grants to Intel to expand U.S. semiconductor production on March 20, 2024, at the Intel Ocotillo Campus in Chandler, Arizona.jpg",
 "File:Rapidus factory under construction.jpg", "File:FTG-15 Flight Test (4108842).jpeg",
 "File:Vandenberg launches SpaceX Falcon 9 (181007-F-XJ735-034).jpg", "File:Kemmerer Power Station under construction - Nov 2024.jpg",
 "File:The Advanced Test Reactor at Idaho National Laboratory (14676550274).jpg", "File:The station pictured from the SpaceX Crew Dragon 5.jpg",
 "File:Narvikbukta Kveldssol.JPG", "File:2019-08-11 Narvik 08.jpg", "File:Nvidia DGX-B200-HGX.jpg", "File:KIOXIA Iwate Kitakami Site.jpg",
 "File:SK Hynix SOCAMM module Computex 2025.jpg", "File:TSMC fabs in Hsinchu 01.jpg", "File:TSMC Fab 14B May 2025 1.jpg",
 "File:South facade of the White House, Washington DC.jpg", "File:WhiteHouseSouthFacadeHDR.jpg",
 "File:NISAR Encapsulated in Payload Fairing at ISRO Launch Site (PIA26611).jpg", "File:KDB HQ.jpg",
 "File:Cern datacenter.jpg", "File:PDC server room.jpg", "File:Datacenter Server Racks (22370909788).jpg", "File:Utah Data Center.jpg",
 "File:Iss072e316172 (Oct 23, 2024) --- The International Space Station is pictured from the SpaceX Dragon crew spacecraft by a SpaceX Crew-8 member shortly after undocking from the Harmony module's space-facing port (cropped).jpg",
 "File:Juelich FZJ JSC a.jpg",
]
out = {}
for i in range(0, len(T), 10):
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "url|size|extmetadata", "iiurlwidth": "1280", "titles": "|".join(T[i:i + 10])}
    try:
        with urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q), headers=UA), timeout=30) as r:
            j = json.loads(r.read())
        for p in j.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {}); g = lambda k: (m.get(k) or {}).get("value", "")
            out[p.get("title")] = {"thumb": ii.get("thumburl"), "w": ii.get("width"), "h": ii.get("height"), "page": ii.get("descriptionurl"),
                                   "lic": g("LicenseShortName"), "artist": g("Artist")[:240], "credit": g("Credit")[:200], "missing": "missing" in p}
    except Exception as e:  # noqa: BLE001
        out[f"err{i}"] = f"{type(e).__name__}: {str(e)[:160]}"
    time.sleep(2)
for k, v in out.items():
    if not isinstance(v, dict) or not v.get("thumb"): continue
    time.sleep(4)
    try:
        with urllib.request.urlopen(urllib.request.Request(v["thumb"], headers=UA), timeout=40) as r:
            v["b64"] = base64.b64encode(r.read()).decode()
    except Exception as e:  # noqa: BLE001
        v["imgerr"] = f"{type(e).__name__}: {str(e)[:120]}"
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
