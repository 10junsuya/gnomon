"""출처 접속 확인(한 번씩). 이번: 국가 프로젝트 사진 1280px 주소가 실제로 열리는지 확인, 화면 점검용으로 잠깐 받아 둠 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, time, urllib.request
from pathlib import Path
UA = {"User-Agent": "GnomonApp/1.0 (https://github.com/10junsuya/gnomon; contact via GitHub issues) python-urllib"}
U = ["https://upload.wikimedia.org/wikipedia/commons/thumb/4/4d/Larry_Ellison_-_American_AI_investment.png/1280px-Larry_Ellison_-_American_AI_investment.png.png"]
out = {}
for u in U:
    time.sleep(5)
    for k in range(2):
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
                out[u] = {"ok": True, "ct": r.headers.get("Content-Type"), "b64": base64.b64encode(r.read()).decode()}
            break
        except Exception as e:  # noqa: BLE001
            out[u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}; time.sleep(20)
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
