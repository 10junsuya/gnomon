"""적중 기록: 노몬 예측 vs 실제 공시 기준가 → data/track.json

- 예측(live): 한국 05:30~09:00 사이(미국 정규장이 끝난 뒤) 실행되면, 오늘 한국 장 날의 기준가 예측을
  그 시각 숫자로 한 번만 저장해요. 저장한 예측은 다시 고치지 않아요.
- 거꾸로 계산(back): 같은 계산을 지난 날짜에 돌려 본 값이에요(백테스트). 지금 구성종목 비중과
  유럽중앙은행 환율을 쓰기 때문에 그날 실제로 보여 준 숫자와는 조금 다를 수 있어요.
- 공시 기준가(공공데이터포털)가 올라오면 실제값과 오차를 채워요.

계산은 앱의 '이어 계산'과 같아요:
  예측 기준가 = 마지막 공시 기준가 × (1 + Σ 비중 × 미국 종가 변화) × (지금 환율 ÷ 그날 환율)
  지수형은 같은 지수 미국 ETF 한 개, 비중형은 담긴 회사들(시세 없는 회사·작은 회사는 받은 회사 평균).
  --backfill: 야후에서 지난 한 달 종가를 받아 거꾸로 계산을 넓혀요(처음 한 번).
"""
import datetime as dt
import json
import re
import sys
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "track.json"
KST = ZoneInfo("Asia/Seoul")
KEEP = 40
TK = lambda t: re.sub(r"[-.]", "", str(t or ""))  # noqa: E731  앱과 같은 종목 이름 맞추기


def load(p, d):
    try:
        return json.loads((ROOT / p).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return d


def kr_holidays():
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const KRX_HOL = \[(.*?)\];", s, re.S)
    return set(re.findall(r'\["(\d{4}-\d{2}-\d{2})"', m.group(1) if m else ""))


KR_HOL = kr_holidays()


def kr_open(d):
    x = dt.date.fromisoformat(d)
    return x.weekday() < 5 and d not in KR_HOL


def models():
    E = load("data/etfs.json", {"groups": {}, "etfs": []})
    H = load("data/holdings.json", {}).get("etfs", {})
    out = {}
    for code, name, group in E["etfs"]:
        G = E["groups"].get(group, {})
        hv = H.get(code) or {}
        kind = hv.get("kind") or G.get("kind") or "index"
        top = [(TK(x["ticker"]), x["weight"] / 100) for x in hv.get("top", []) if x.get("ticker")]
        out[code] = {"name": name, "kind": kind, "proxy": TK(hv.get("proxy") or G.get("proxy") or ""), "top": top,
                     "restw": (hv.get("rest_weight") or 0) / 100, "cc": G.get("cc"), "hedge": bool(G.get("hedge")),
                     "asia": round(hv.get("asia_weight") or 0, 1), "active": "액티브" in name}
    return out


def cc_f(m, r):
    c = m.get("cc")
    if not c or r is None:
        return r
    return min(r, c["cap"]) if c.get("type") == "cap" else (r * c["p"] if r > 0 else r)


class Px:
    """날짜별 미국 종가 (앱과 같은 이름: BRK-B → BRKB)"""

    def __init__(self, closes):
        self.c = {d: {TK(t): v for t, v in row.items()} for d, row in closes.items()}
        # 대표 승인 21번(2026-11-19): 토·일 날짜, 종목이 거의 없는 날짜(예: 11/15 일요일 SMERY 1종목)는
        # '직전 미국 날짜'로 쓰지 않아요 — 그 칸 하나 때문에 하루 예측이 통째로 빠졌어요
        ns = sorted(len(r) for r in self.c.values() if r)
        med = ns[len(ns) // 2] if ns else 0
        self.ok = {d for d, r in self.c.items()
                   if dt.date.fromisoformat(d).weekday() < 5 and len(r) >= max(3, 0.3 * med)}

    def days(self):
        return sorted(self.ok)

    def get(self, t, d):
        v = self.c.get(d, {}).get(t)
        return v if isinstance(v, (int, float)) and v > 0 else None

    def prev(self, d):
        ks = [x for x in self.ok if x < d]
        return max(ks) if ks else None


def factor(m, px, u0, u1):
    """u0 종가 → u1 종가 사이 이 ETF의 미국 자산 변화 (1 + 변화율). 계산할 수 없으면 None"""
    if not u0 or not u1:
        return None
    if u0 == u1:
        return 1.0
    if m["kind"] != "pdf":
        a, b = px.get(m["proxy"], u0), px.get(m["proxy"], u1)
        return 1 + cc_f(m, b / a - 1) if a and b else None
    sw = sc = miss = 0.0
    for t, w in m["top"]:
        a, b = px.get(t, u0), px.get(t, u1)
        if a and b:
            sw += w; sc += w * (b / a - 1)
        else:
            miss += w
    if sw <= 0 or sw < 0.5 * (sw + miss):  # 받은 종목이 절반도 안 되면 기록하지 않아요
        return None
    r = sc + (miss + m["restw"]) * (sc / sw)
    return 1 + cc_f(m, r)


def fx_at(hist, d):
    ks = [k for k in hist if k <= d]
    return hist[max(ks)] if ks else None


def yahoo_fx():
    try:
        u = "https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?range=1d&interval=5m"
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0 (gnomon-track)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            v = json.loads(r.read())["chart"]["result"][0]["meta"]["regularMarketPrice"]
        return float(v) if v and 800 < v < 2500 else None
    except Exception:  # noqa: BLE001
        return None


def entry(kind, base, target, base_nav, pred_nav, made, u_from, u_to, fx_from, fx_to):
    return {"kind": kind, "base": base, "target": target, "base_nav": round(base_nav, 2), "pred_nav": round(pred_nav, 2),
            "made": made, "us": [u_from, u_to], "fx": [round(fx_from, 2) if fx_from else None, round(fx_to, 2) if fx_to else None]}


def tag(m, e):
    """대표 승인 34번(2026-11-22): 아시아 몫(%)은 예측에 0% 변화로 들어가요 · 액티브 ETF는 비중이 자주 바뀌어 back 은 평균에서 빼요"""
    if m.get("asia"):
        e["asia"] = m["asia"]
    if m.get("active"):
        e["active"] = 1
    return e


def fill(e, rows):
    """공시 기준가가 나왔으면 실제값·오차를 채워요 (전날 공시 기준가 대비 등락률로 비교)"""
    by = {r["d"]: r["nav"] for r in rows if r.get("nav")}
    if e["target"] not in by:
        return
    prev = [d for d in by if d < e["target"]]
    if not prev:
        return
    p = by[max(prev)]
    e["actual_nav"] = round(by[e["target"]], 2)
    e["prev_nav"] = round(p, 2)
    e["pred_pct"] = round((e["pred_nav"] / p - 1) * 100, 3)
    e["actual_pct"] = round((e["actual_nav"] / p - 1) * 100, 3)
    e["err"] = round(e["pred_pct"] - e["actual_pct"], 3)


def main():
    backfill = "--backfill" in sys.argv
    live = load("data/live.json", {})
    rows_all = live.get("kr", {})
    hist = (live.get("fx") or {}).get("hist", {})
    closes = dict(live.get("closes", {}))
    M = models()
    old = load("data/track.json", {})
    T = {c: list(v) for c, v in (old.get("etfs") or {}).items()}

    if backfill:  # 지난 한 달 종가를 야후에서 받아 거꾸로 계산 범위를 넓혀요
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from fetch_live import daily_closes  # noqa: E402
        names = sorted({m["proxy"] for m in M.values() if m["kind"] != "pdf" and m["proxy"]} |
                       {t for m in M.values() if m["kind"] == "pdf" for t, _ in m["top"]})
        from us_sym import US_SYM as alias  # noqa: E402  앱(index.html US_SYM)과 같은 표 (대표 승인 23번)
        got = 0
        for t in names:
            for d, v in (daily_closes(alias.get(t, t)) or {}).items():
                closes.setdefault(d, {}).setdefault(t, v); got += 1
        print(f"지난 종가 {len(names)}종목 · {got}칸")
    px = Px(closes)
    now = dt.datetime.now(KST)
    made = now.strftime("%Y-%m-%d %H:%M")

    # 1) 거꾸로 계산: 공시 기준가가 연달아 있는 날마다
    nb = 0
    for code, m in M.items():
        rows = [r for r in rows_all.get(code, []) if r.get("nav")]
        have = {e["target"] for e in T.get(code, [])}
        for r0, r1 in zip(rows, rows[1:]):
            if r1["d"] in have:
                continue
            u0, u1 = px.prev(r0["d"]), px.prev(r1["d"])
            f = factor(m, px, u0, u1)
            f0, f1 = fx_at(hist, r0["d"]), fx_at(hist, r1["d"])
            if f is None or (not m["hedge"] and not (f0 and f1)):
                continue
            pred = r0["nav"] * f * (1 if m["hedge"] else f1 / f0)
            T.setdefault(code, []).append(tag(m, entry("back", r0["d"], r1["d"], r0["nav"], pred, made, u0, u1, f0, f1))); nb += 1

    # 2) 오늘 예측 저장: 한국 05:30~09:00, 오늘이 한국 장 날이고 미국 종가가 들어와 있을 때 한 번만
    nl = 0
    today = now.date().isoformat()
    if kr_open(today) and dt.time(5, 30) <= now.time() < dt.time(9, 0):
        u_to = px.prev(today)
        fx_now = yahoo_fx() or (live.get("fx") or {}).get("rate")
        for code, m in M.items():
            if any(e["target"] == today and e["kind"] == "live" for e in T.get(code, [])):
                continue
            rows = [r for r in rows_all.get(code, []) if r.get("nav") and r["d"] < today]
            if not rows:
                continue
            r0 = rows[-1]
            u0 = px.prev(r0["d"])
            f = factor(m, px, u0, u_to)
            f0 = fx_at(hist, r0["d"])
            if f is None or (not m["hedge"] and not (f0 and fx_now)):
                continue
            pred = r0["nav"] * f * (1 if m["hedge"] else fx_now / f0)
            # 오늘 하루 예상 등락률: 전날(한국 장 날) 기준가 추정 대비 — 공시가 하루 늦어 전날 것도 이어 계산해요
            prev_kr = (dt.date.fromisoformat(today) - dt.timedelta(days=1)).isoformat()
            while not kr_open(prev_kr):
                prev_kr = (dt.date.fromisoformat(prev_kr) - dt.timedelta(days=1)).isoformat()
            fp, fxp = factor(m, px, u0, px.prev(prev_kr)), fx_at(hist, prev_kr)
            prev_nav = r0["nav"] if r0["d"] == prev_kr else (r0["nav"] * fp * (1 if m["hedge"] else fxp / f0) if fp and (m["hedge"] or fxp) else None)
            T[code] = [e for e in T.get(code, []) if e["target"] != today]  # 거꾸로 계산 값보다 그날 저장 값이 우선
            en = tag(m, entry("live", r0["d"], today, r0["nav"], pred, made, u0, u_to, f0, fx_now))
            if prev_nav:
                en["day_pct"] = round((pred / prev_nav - 1) * 100, 3)
            T[code].append(en); nl += 1

    # 3) 실제값 채우기 + 정리
    for code, es in T.items():
        for e in es:
            if code in M:
                tag(M[code], e)
            if "actual_nav" not in e:
                fill(e, rows_all.get(code, []))
        es.sort(key=lambda e: e["target"])
        T[code] = es[-KEEP:]
    out = {"updated_kst": made,
           "how": "예측 기준가 = 마지막 공시 기준가 × 미국 종가 변화(구성 비중) × 환율 변화. "
                  "live = 그날 아침(미국 장 마감 뒤) 저장한 값, back = 같은 계산을 지난 날짜에 돌려 본 값(지금 비중·유럽중앙은행 환율). "
                  "asia = 예측에 0% 변화로 들어간 아시아 상장 몫(%), active = 액티브 ETF(back 은 평균에서 뺌). "
                  "오차 = 예측 등락률 − 실제 등락률(전날 공시 기준가 대비, %p).",
           "etfs": T}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    done = [e for es in T.values() for e in es if "err" in e and not (e.get("active") and e["kind"] == "back")]
    mae = sum(abs(e["err"]) for e in done) / len(done) if done else 0
    print(f"적중 기록: 거꾸로 {nb}건 추가 · 오늘 예측 {nl}건 저장 · 채점 {len(done)}건 · 평균 오차 {mae:.2f}%p")


if __name__ == "__main__":
    main()
