"""출처 접속 확인(한 번씩). 이번: 환율 시험(승인 34번 ①) — 한국 펀드가 기준가에 쓰는 환율 후보. 결과 → data/probe.json"""
import json, urllib.request
from pathlib import Path
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
      "Accept": "application/json,text/plain,*/*", "Accept-Language": "en-US,en;q=0.9"}
def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=30) as r:
        return r.read().decode("utf-8", "replace")
E = "https://ecos.bok.or.kr/api/StatisticSearch/sample/json/kr/1/10/731Y001/D/{}/{}/0000001"  # 한국은행 원/달러 매매기준율(공개 예시 키, 10줄)
out = {}
for k, u in {"ecos_a": E.format("20261020", "20261031"), "ecos_b": E.format("20261101", "20261112"),
             "ecos_c": E.format("20261113", "20261122"),
             "yahoo_1h": "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?range=1mo&interval=1h",
             "frankfurter": "https://api.frankfurter.dev/v1/2026-10-20..?base=USD&symbols=KRW"}.items():
    try:
        b = get(u); out[k] = {"len": len(b), "body": b[:200000]}
    except Exception as e:  # noqa: BLE001
        out[k] = {"err": f"{type(e).__name__}: {str(e)[:160]}"}
Path("data/probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
