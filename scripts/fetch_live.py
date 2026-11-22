"""밤사이 예상 계산에 쓰는 숫자 모으기 → data/live.json

GitHub Actions에서 하루 몇 번 돌아요. 키는 GitHub Secrets 환경변수로만 들어오고 파일·로그에 남기지 않아요.
- 미국 시세: Finnhub (구성종목 + 같은 지수 미국 ETF SPY·QQQ·SOXQ)
- 미국 종가 기록: 시세에서 나온 종가/전일 종가를 날짜별로 쌓아요(최근 20거래일)
- 국내 ETF 기준가·종가: 공공데이터포털 금융위원회 증권상품시세 (보통 하루 늦게 올라와요)
- 원/달러: 유럽중앙은행 기준환율(하루 한 번) 최근 기록
앱은 이 파일을 내장해서, 실시간 서버에 못 붙는 곳(미리보기 등)에서도 '언제 기준 숫자인지' 밝히고 보여줘요.
"""
import datetime as dt
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
import sys
import time
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etf_list import ETFS as ETF_LIST, GROUPS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "live.json"
HOLD = ROOT / "data" / "holdings.json"
KST, NY = ZoneInfo("Asia/Seoul"), ZoneInfo("America/New_York")
FINNHUB_KEY = os.environ.get("FINNHUB_API_KEY", "").strip()
DATA_KEY = urllib.parse.unquote(os.environ.get("DATA_GO_KR_API_KEY", "").strip())
ETF_URL = "https://apis.data.go.kr/1160100/GetSecuritiesProductInfoService_V2/getETFPriceInfo_V2"
KR_ETFS = [c for c, _, _ in ETF_LIST]
PROXIES = sorted({g["proxy"] for g in GROUPS.values() if g.get("proxy")})
KEEP = 30  # 종가 기록 일수


def scrub(t):
    for k in (FINNHUB_KEY, DATA_KEY, urllib.parse.quote(DATA_KEY, safe=""), urllib.parse.quote_plus(DATA_KEY)):
        if k:
            t = t.replace(k, "***")
    return t


def get(url, timeout=25):
    req = urllib.request.Request(url, headers={"User-Agent": "gnomon/0.1 (+github.com/10junsuya/gnomon)"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def us_closed_days():
    s = (ROOT / "index.html").read_text(encoding="utf-8")
    m = re.search(r"const US_HOL = \[(.*?)\];", s, re.S)
    return {d for d, kind in re.findall(r'\["(\d{4}-\d{2}-\d{2})","[^"]*","(closed|early)"', m.group(1) if m else "") if kind == "closed"}


US_CLOSED = us_closed_days()


def us_trading(d):
    return d.weekday() < 5 and d.isoformat() not in US_CLOSED


def prev_us(d):
    d -= dt.timedelta(days=1)
    while not us_trading(d):
        d -= dt.timedelta(days=1)
    return d


def us_lag(d, now_ny):
    """시세 날짜 d 가 지금 기준 '가장 최근 미국 장 날'보다 몇 거래일 뒤처졌는지"""
    t = now_ny.date()
    latest = t if (us_trading(t) and (now_ny.hour, now_ny.minute) >= (9, 30)) else prev_us(t)
    n = 0
    while latest > d and n < 30:
        latest = prev_us(latest); n += 1
    return n


def tickers():
    out = list(PROXIES)
    try:
        h = json.loads(HOLD.read_text(encoding="utf-8"))
        for v in h.get("etfs", {}).values():
            out += [i["ticker"] for i in v.get("top", []) if i.get("ticker")]
    except (OSError, ValueError):
        pass
    # 노몬 ETF에 담기지 않았어도 앱 회사 화면에 있는 회사(MSTR·FSLR 등)는 시세를 받아요 (대표 결정 2026-11-22, 31번)
    try:
        have = {re.sub(r"[-.]", "", t) for t in out}
        co = json.loads((ROOT / "data" / "companies.json").read_text(encoding="utf-8")).get("co", {})
        out += [t for t in co if re.fullmatch(r"[A-Z]{1,6}", t) and t not in have]
    except (OSError, ValueError):
        pass
    seen = []
    for t in out:
        if t not in seen:
            seen.append(t)
    return seen[:300]


BACK_DAYS = 8  # 이어 계산에 쓰는 최근 미국 장 날 수
BROWSER = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36",
           "Accept": "application/json,text/plain,*/*"}


def daily_closes(t):
    """한 종목의 최근 한 달 정규장 종가 {날짜: 종가}. 야후 → 나스닥 순으로 시도."""
    try:
        u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?range=1mo&interval=1d"
        with urllib.request.urlopen(urllib.request.Request(u, headers=BROWSER), timeout=20) as r:
            res = json.loads(r.read())["chart"]["result"][0]
        ts, cl = res.get("timestamp") or [], res["indicators"]["quote"][0].get("close") or []
        out = {dt.datetime.fromtimestamp(a, NY).date().isoformat(): round(b, 4) for a, b in zip(ts, cl) if b}
        if out:
            return out
    except Exception:  # noqa: BLE001
        pass
    for cls in ("stocks", "etf"):
        try:
            u = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(t.replace('-', '.'))}/historical?assetclass={cls}&limit=30&fromdate=" + (dt.date.today() - dt.timedelta(days=40)).isoformat()
            with urllib.request.urlopen(urllib.request.Request(u, headers=BROWSER), timeout=20) as r:
                rows = ((json.loads(r.read()).get("data") or {}).get("tradesTable") or {}).get("rows") or []
            out = {}
            for x in rows:
                m, d, y = x["date"].split("/")
                out[f"{y}-{m}-{d}"] = float(x["close"].replace("$", "").replace(",", ""))
            if out:
                return out
        except Exception:  # noqa: BLE001
            continue
    return {}


def backfill(closes, names, errors):
    """기록이 빠진 최근 미국 장 날 종가를 채워요(이미 있는 값은 그대로). 오늘 장중 값은 넣지 않아요."""
    now_ny = dt.datetime.now(NY)
    today = now_ny.date()
    d = today if (us_trading(today) and now_ny.hour >= 16) else prev_us(today)
    days = []
    while len(days) < BACK_DAYS:
        days.append(d.isoformat()); d = prev_us(d)
    need = [t for t in names if any(t not in closes.get(x, {}) for x in days)]
    filled = 0
    for t in need:
        time.sleep(0.4)
        got = daily_closes(t)
        if not got:
            errors.append(f"{t}: 지난 종가 못 받음")
            continue
        for x in days:
            if x in got and t not in closes.get(x, {}):
                closes.setdefault(x, {})[t] = got[x]; filled += 1
    if need:
        print(f"지난 종가 채움: {len(need)}종목 확인 · {filled}칸")
    return closes


def yahoo_quote(t):
    """Finnhub 무료 요금제에 없는 종목(장외 거래 ADR 등)은 야후 파이낸스 일봉으로 대신 받아요."""
    u = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(t)}?range=5d&interval=1d"
    m = json.loads(get(u))["chart"]["result"][0]["meta"]
    p, pc, tm = m.get("regularMarketPrice"), m.get("chartPreviousClose") or m.get("previousClose"), m.get("regularMarketTime")
    if not (p and tm):
        return None
    return {"c": p, "pc": pc, "dp": (p / pc - 1) * 100 if pc else None, "t": tm}


def quotes(old, errors):
    q, closes = {}, {k: dict(v) for k, v in old.get("closes", {}).items()}
    if not FINNHUB_KEY:
        errors.append("FINNHUB_API_KEY 없음")
        return old.get("quotes", {}), closes
    now_ny = dt.datetime.now(NY)
    stale = []
    for t in tickers():
        time.sleep(1.05)  # 무료 한도: 1분에 60번
        try:
            j = json.loads(get("https://finnhub.io/api/v1/quote?" + urllib.parse.urlencode({"symbol": t, "token": FINNHUB_KEY})))
        except Exception as e:  # noqa: BLE001 — 순간 연결 끊김이면 야후로, 그것도 안 되면 지난 값 유지 (2026-11-17)
            errors.append(scrub(f"{t}: {type(e).__name__}: {e}")[:160])
            j = None
        # Finnhub 값이 하루 넘게 지난 날짜면(장외 ADR 등, 예: SMERY) 야후도 받아 더 새 값을 써요 (2026-11-20 대표 승인)
        if j and j.get("c") and j.get("t"):
            fd = dt.datetime.fromtimestamp(j["t"], dt.timezone.utc).astimezone(NY).date()
            if us_lag(fd, now_ny) >= 1:
                try:
                    y = yahoo_quote(t)
                except Exception:  # noqa: BLE001
                    y = None
                if y and y["t"] > j["t"]:
                    j = y
        if not j or not j.get("c") or not j.get("t"):
            try:
                j = yahoo_quote(t)
            except Exception:  # noqa: BLE001
                j = None
            if not j:
                prev = (old.get("quotes") or {}).get(t)
                if prev:
                    q[t] = {**prev, "stale": True}  # 지난 값 그대로(화면이 비지 않게). 다음 수집에서 새 값으로 바뀌어요
                    errors.append(f"{t}: 이번엔 못 받아 지난 값 유지 ({prev.get('d')})")
                else:
                    errors.append(f"{t}: 값 없음 (Finnhub·야후 모두)")
                continue
        ts = dt.datetime.fromtimestamp(j["t"], dt.timezone.utc).astimezone(NY)
        d = ts.date()
        q[t] = {"p": j["c"], "pc": j.get("pc"), "dp": j.get("dp"), "t": ts.isoformat(timespec="minutes"), "d": d.isoformat()}
        # 대표 승인 22번(2026-11-19): 시세 날짜가 미국 장 날로 이틀 넘게 지났으면 오류로 남기고 화면에 '지난 값' 표시
        lag = us_lag(d, now_ny)
        if lag >= 2:
            q[t]["old"] = True
            stale.append(f"{t}: 시세가 {lag}거래일 지난 값 ({d.isoformat()} 뉴욕)")
        if j.get("pc"):
            closes.setdefault(prev_us(d).isoformat(), {})[t] = j["pc"]
        session_over = now_ny.date() > d or now_ny.hour >= 16
        # 대표 승인 21번(2026-11-19): 토·일·미국 휴장일 날짜로는 종가 칸을 만들지 않아요(장외 종목 시각이 주말로 찍힐 때)
        if session_over and us_trading(d):
            closes.setdefault(d.isoformat(), {})[t] = j["c"]
    errors[:0] = stale  # 오래된 시세는 앞에 둬요(오류 목록은 20개까지만 저장)
    closes = backfill(closes, list(q) or list(old.get("quotes", {})), errors)
    # 이미 쌓인 기록에서도 장이 없던 날짜 칸은 지워요(승인 21번)
    closes = {k: v for k, v in closes.items() if us_trading(dt.date.fromisoformat(k))}
    closes = dict(sorted(closes.items())[-KEEP:])
    return (q or old.get("quotes", {})), closes


def logos(old, errors):
    """회사 로고 주소(Finnhub 회사 정보). 그림은 복사하지 않고 주소만 저장해요."""
    out = dict(old.get("logos", {}))
    if not FINNHUB_KEY:
        return out
    n = 0
    for t in tickers():
        if t in out or n >= 40:
            continue
        n += 1
        time.sleep(1.05)
        try:
            j = json.loads(get("https://finnhub.io/api/v1/stock/profile2?" + urllib.parse.urlencode({"symbol": t, "token": FINNHUB_KEY})))
            u = (j or {}).get("logo") or ""
            out[t] = u if u.startswith("https://") else ""
        except Exception as e:  # noqa: BLE001
            errors.append(scrub(f"로고 {t}: {type(e).__name__}")[:80])
    return out


def kr_navs(old, errors):
    out = {c: list(v) for c, v in old.get("kr", {}).items()}
    if not DATA_KEY:
        errors.append("DATA_GO_KR_API_KEY 없음")
        return out
    begin = (dt.datetime.now(KST) - dt.timedelta(days=40)).strftime("%Y%m%d")
    for code in KR_ETFS:
        try:
            url = ETF_URL + "?" + urllib.parse.urlencode({"serviceKey": DATA_KEY, "resultType": "json", "numOfRows": 40, "pageNo": 1, "likeSrtnCd": code, "beginBasDt": begin})
            for k in range(3):  # 공공데이터 서버가 가끔 늦게 답해서 두 번 더 시도해요
                try:
                    body = get(url, timeout=40); break
                except (urllib.error.URLError, TimeoutError):
                    if k == 2:
                        raise
                    time.sleep(3)
            j = json.loads(body)
            items = j["response"]["body"].get("items", {}) or {}
            items = items.get("item", []) if isinstance(items, dict) else items
            items = [items] if isinstance(items, dict) else items
            rows = {r["d"]: r for r in out.get(code, [])}
            for i in items:
                if str(i.get("srtnCd", "")).upper() != code.upper():
                    continue
                d = i["basDt"]
                rows[f"{d[:4]}-{d[4:6]}-{d[6:]}"] = {"d": f"{d[:4]}-{d[4:6]}-{d[6:]}", "nav": float(i["nav"]), "close": float(i["clpr"])}
            out[code] = sorted(rows.values(), key=lambda r: r["d"])[-25:]
        except Exception as e:  # noqa: BLE001
            errors.append(scrub(f"{code}: {type(e).__name__}: {e}")[:160])
    return out


def fx(old, errors):
    try:
        start = (dt.date.today() - dt.timedelta(days=45)).isoformat()
        j = json.loads(get(f"https://api.frankfurter.dev/v1/{start}..?base=USD&symbols=KRW"))
        hist = {d: r["KRW"] for d, r in j.get("rates", {}).items()}
        hist = dict(sorted({**old.get("fx", {}).get("hist", {}), **hist}.items())[-KEEP:])
        last = max(hist)
        return {"rate": hist[last], "date": last, "src": "유럽중앙은행 기준환율", "live": False, "hist": hist}
    except Exception as e:  # noqa: BLE001
        errors.append(f"환율: {type(e).__name__}: {str(e)[:120]}")
        return old.get("fx", {})


def main():
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    errors = []
    q, closes = quotes(old, errors)
    out = {"generated_at_kst": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "quotes": q, "closes": closes,
           "kr": kr_navs(old, errors), "fx": fx(old, errors), "logos": logos(old, errors), "errors": errors[:20]}
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"시세 {len(q)}개 · 종가 {len(closes)}일 · 국내 {sum(1 for v in out['kr'].values() if v)}개 · 오류 {len(errors)}")
    for e in errors:
        print(" -", e)


if __name__ == "__main__":
    main()
