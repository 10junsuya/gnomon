"""출처 접속 확인(한 번씩). 이번: 백악관 공식 사진(미국 정부 저작물) 스타게이트 발표 장면 확인 (대표 요청 2026-11-22). 결과 → data/probe.json"""
import base64, json, urllib.request
from pathlib import Path
UA = {"User-Agent": "Mozilla/5.0 GnomonApp/1.0"}
out = {}
for u in ["https://live.staticflickr.com/65535/54346296638_1f1e27b48d_b.jpg"]:
    try:
        with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=40) as r:
            out[u] = {"ok": True, "b64": base64.b64encode(r.read()).decode()}
    except Exception as e:  # noqa: BLE001
        out[u] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:120]}"}
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
