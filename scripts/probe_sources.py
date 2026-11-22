"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 사진 원본 크기·라이선스 확인 (고화질로 바꾸기, 대표 요청 2026-11-22). 결과 → data/probe.json"""
import json, time, urllib.parse, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; contact via GitHub issues) python-urllib"}
T = [
 "File:Larry Ellison - American AI investment.png",
 "File:President Donald Trump signs Executive Orders at the White House AI Summit at Andrew W. Mellon Auditorium in Washington (54677035188).jpg",
 "File:Frontier supercomputer (52291130197).jpg",
 "File:Gas centrifuge cascade.jpg",
 "File:President Joe Biden announces CHIPS and Science Act grants to Intel to expand U.S. semiconductor production on March 20, 2024, at the Intel Ocotillo Campus in Chandler, Arizona.jpg",
 "File:Donald Trump state visit to Saudi Arabia, 2025-05-13 P20250513DT-0251.jpg",
 "File:2019-08-11 Narvik 08.jpg",
 "File:JUPITER racks with logos of supporters and partners. Copyright- Forschungszentrum Jülich - Sascha Kreklau.jpg",
 "File:Nvidia DGX-B200-HGX.jpg",
 "File:Google Data Center, Council Bluffs Iowa (49062863796).jpg",
 "File:KDB HQ.jpg",
 "File:231105-1 TSMC Fab 21 construction.jpg",
 "File:TSMC Fab 18 and fields May 2025.jpg",
 "File:Intel Ohio One (2024-02-11-04-16-53 UMBRA-06).tiff",
 "File:KIOXIA Iwate Kitakami Site.jpg",
 "File:SK Hynix SOCAMM module Computex 2025.jpg",
 "File:Rapidus factory under construction.jpg",
 "File:JASM Kumamoto 2024 03.jpg",
 "File:TSMC fabs in Hsinchu 01.jpg",
 "File:Artemis II Launch (NHQ202604010307).jpg",
 "File:Blue Ghost M1 on the Moon.png",
 "File:FTG-15 Flight Test (4108842).jpeg",
 "File:Vandenberg launches SpaceX Falcon 9 (181007-F-XJ735-034).jpg",
 "File:The station pictured from the SpaceX Crew Dragon 5.jpg",
 "File:Iss072e316172 (Oct 23, 2024) --- The International Space Station is pictured from the SpaceX Dragon crew spacecraft by a SpaceX Crew-8 member shortly after undocking from the Harmony module's space-facing port (cropped).jpg",
 "File:KSLV-II Nuri and the launchpad 01.jpg",
 "File:NISAR Encapsulated in Payload Fairing at ISRO Launch Site (PIA26611).jpg",
 "File:Construction at Vogtle Unit 3 - August 2013 (14676545094).jpg",
 "File:Three Mile Island (color).jpg",
 "File:The Advanced Test Reactor at Idaho National Laboratory (14676550274).jpg",
 "File:Kemmerer Power Station under construction - Nov 2024.jpg",
 "File:Overview of cooling towers of Dukovany Nuclear Power Station near Dukovany, Třebíč District.jpg",
 "File:Three Mile Island Nuclear Generating Station (51142893665).jpg",
 "File:TerraPower Signing Ceremony-0124 (55140163015).jpg",
 "File:TerraPower Signing Ceremony-0151 (55140163535).jpg",
 "File:Joe Biden at the TSMC Semiconductor Plant in Phoenix (P20221206AS-0794).jpg"
]
out = {}
for i in range(0, len(T), 15):
    q = {"action": "query", "format": "json", "prop": "imageinfo", "iiprop": "size|extmetadata", "titles": "|".join(T[i:i + 15])}
    try:
        with urllib.request.urlopen(urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(q), headers=UA), timeout=30) as r:
            j = json.loads(r.read())
        for p in j.get("query", {}).get("pages", {}).values():
            ii = (p.get("imageinfo") or [{}])[0]; m = ii.get("extmetadata", {}); g = lambda k: (m.get(k) or {}).get("value", "")
            out[p.get("title")] = {"w": ii.get("width"), "h": ii.get("height"), "lic": g("LicenseShortName"), "artist": g("Artist")[:200], "missing": "missing" in p}
    except Exception as e:  # noqa: BLE001
        out[f"err{i}"] = f"{type(e).__name__}: {str(e)[:160]}"
    time.sleep(2)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
