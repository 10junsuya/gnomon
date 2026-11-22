"""ETF 구성종목(PDF) → data/holdings.json (이후 check_data.py --embed 로 앱에 반영)

1순위: FunETF의 ETF별 구성종목 표 (각 ETF가 실제로 담은 종목·비중)
2순위(실패 시): S&P500은 SPY, 나스닥100은 QQQ 공시 보유종목 / 우주항공TOP10은 신한자산운용 사이트
실패해도 기존 값을 지우지 않고 오류만 기록해요. 하루 한 번만 받아요.
"""
import csv, datetime as dt, html, http.cookiejar, io, json, re, sys, time, urllib.error, urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from etf_list import ETFS, GROUPS, isin  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "holdings.json"
KST = dt.timezone(dt.timedelta(hours=9))
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36 gnomon/0.2",
      "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8"}
OP = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
TOP_PDF = 25    # 비중형은 위에서 25개까지만 하나씩, 나머지 비중은 받은 종목 평균으로 채워요
TOP_INDEX = 15  # 지수형은 위에서 15개만 하나씩 계산하고 나머지는 같은 지수 미국 ETF 움직임에 맞춰요
ISIN_ALIAS = {"US25460G2865": ("TSLL", "Direxion Daily TSLA Bull 2X", "테슬라 2배 ETF"),
              "US64119N6085": ("NTSK", "Netskope", ""), "US88025T1025": ("TENB", "Tenable", ""), "US78781J1097": ("SAIL", "SailPoint", ""),
              "US7534221046": ("RPD", "Rapid7", ""), "US68287N1000": ("OSPN", "OneSpan", ""), "US87969B1017": ("TLS", "Telos", ""),
              "CA8795123097": ("TSAT", "Telesat", ""), "CA2483561072": ("DNN", "Denison Mines", ""), "CA91688R1082": ("URG", "Ur-Energy", ""),
              "CA29259W7008": ("EU", "enCore Energy", ""), "US37954Y8306": ("COPX", "Global X Copper Miners ETF", "구리 광산 ETF")}
NAME_FIX = {"SIEMENS ENERGY": "SMERY"}  # 미국에 같은 표기의 다른 회사가 있는 경우: 미국 ADR로
ASIA_SFX = {"JP", "HK", "TT", "KS", "KQ", "CH", "C1", "C2", "SP", "AU", "IN"}   # 아시아 거래소: 낮에 거래돼서 밤사이 변화 없음
SAME_ADR = {"ASML", "SAP", "NOK", "STM", "ARM", "TSM", "SHOP", "SPOT", "NVO", "AZN", "SNY", "TM", "SONY", "BABA"}  # 유럽 등 본국 표기와 미국 표기가 같은 종목  # 종목코드 없이 ISIN만 나오는 미국 상장 상품
NAME2TICKER = {"space exploration technologies": "SPCX", "rocket lab": "RKLB", "viasat": "VSAT", "ast spacemobile": "ASTS",
               "firefly aerospace": "FLY", "planet labs": "PL", "intuitive machines": "LUNR", "redwire": "RDW", "blacksky": "BKSY", "satellogic": "SATL"}


def get(url, timeout=40, tries=3):
    # 429(너무 자주 물음)·503 이면 잠깐 쉬었다 다시 물어요 (승인 30번, 2026-11-22)
    for k in range(tries):
        try:
            with OP.open(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 503) or k == tries - 1:
                raise
            ra = e.headers.get("Retry-After", "") if e.headers else ""
            wait = min(60, int(ra)) if ra.isdigit() else 10 * (k + 1)
            print(f"  {e.code} → {wait}초 쉬고 다시 ({k + 1}/{tries - 1})")
            time.sleep(wait)


def num(x):
    try:
        return float(str(x).replace(",", "").replace("%", "").strip())
    except ValueError:
        return None


def funetf(code):
    page = get(f"https://www.funetf.co.kr/product/etf/view/{isin(code)}").decode("utf-8", "replace")
    items, other, asia, isin_rest = [], [], [], []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", c))).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        cells = [c for c in cells if c]
        if len(cells) < 2:
            continue
        m = re.fullmatch(r"(.+?)\s*\(([A-Z][A-Z0-9.\-/]{0,9})(?:\s+([A-Z][A-Z0-9]))?\)", cells[0])
        w = num(cells[1])
        alias = next((t for k, t in ISIN_ALIAS.items() if k in cells[0]), None)
        if alias and w and w > 0:
            items.append({"ticker": alias[0], "name": alias[1], "ko": alias[2], "weight": w}); continue
        kr_etf = re.search(r"미국(나스닥100|S&P500)", cells[0]) if not m else None
        if kr_etf and w and w > 0:  # 국내 상장 미국 지수 ETF를 담은 경우: 같은 지수 미국 ETF로 계산
            items.append({"ticker": "QQQ" if kr_etf.group(1) == "나스닥100" else "SPY", "name": cells[0], "ko": cells[0].split(" (")[0], "weight": w}); continue
        if m and m.group(3) and m.group(3) != "US" and w and w > 0:  # 미국 밖 거래소 표기
            if m.group(3) in ASIA_SFX:
                asia.append([cells[0], w]); continue
            if m.group(2) not in SAME_ADR:
                isin_rest.append([cells[0], w]); continue  # 미국에 같은 이름 종목이 따로 있을 수 있어서, 받은 종목 평균으로 채워요
        if not m and w and w > 0 and re.search(r"\(US[0-9A-Z]{9}\d\)|\(CA[0-9A-Z]{9}\d\)", cells[0]):
            isin_rest.append([cells[0], w]); continue  # 종목코드 없이 국제번호만 나온 미국·캐나다 상장 종목: 받은 종목 평균으로
        if not m and w and w > 0 and (re.search(r"\((\d[0-9A-Z]{2,5})(\s+[A-Z][A-Z0-9])?\)\s*$", cells[0]) or "(KR4" in cells[0]) and "KRD" not in cells[0]:
            asia.append([cells[0], w]); continue  # 아시아 거래소 종목: 낮에 거래돼서 밤사이 움직임은 없어요
        if not m or w is None or w <= 0:
            if w is not None and len(other) < 25:
                other.append(cells[:4])  # 종목코드가 없는 줄(옵션·채권·해외 주식 등) — 확인용으로 남겨요
            continue
        # 이름 칸: "한글/영어", "영어/한글", "COCA-COLA CO/THE" 처럼 순서·모양이 섞여 와요 (2026-11-18 승인 18번)
        parts = [p.strip() for p in m.group(1).split("/") if p.strip()]
        ko = next((p for p in parts if re.search(r"[가-힣]", p)), "")
        en = [p for p in parts if not re.search(r"[가-힣]", p)]
        if len(en) > 1 and en[-1].upper() == "THE":
            en = [en[-1] + " " + en[0]] + en[1:-1]
        if len(en) > 1 and (re.fullmatch(r"[A-Z]{2}", en[-1]) or en[-1].upper() in ("CANADA", "BERMUDA", "NETHERLANDS", "IRELAND", "JERSEY", "LUXEMBOURG", "SWITZERLAND", "UK", "CAYMAN ISLANDS")):
            en = en[:-1]  # "Sandisk Corp/DE", "Energy Fuels Inc/Canada" — 뒤에 붙은 설립지 표기는 빼요
        nm = " / ".join(en).replace("_", " ") if en else (ko or m.group(1).strip())
        tk = next((t for k, t in NAME_FIX.items() if k in nm.upper()), m.group(2).replace(".", "-").replace("/", "-"))
        items.append({"ticker": tk, "name": nm, "ko": ko, "weight": w})
    d = re.search(r"구성종목[^<]{0,40}?(20\d{2}[.\-/]\d{1,2}[.\-/]\d{1,2})", page)
    funetf.other, funetf.asia, funetf.isin_rest = other, asia, isin_rest
    for i in items:  # 지수 선물은 같은 지수 미국 ETF로 바꿔서 계산해요
        f = re.fullmatch(r"(NQ|ES)[FGHJKMNQUVXZ]\d", i["ticker"])
        if f:
            i["ticker"], i["ko"] = ("QQQ", "나스닥100 선물") if f.group(1) == "NQ" else ("SPY", "S&P500 선물")
    return (d.group(1) if d else ""), items


def spy():
    import openpyxl  # noqa: PLC0415
    raw = get("https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/holdings-daily-us-en-spy.xlsx")
    rows = list(openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True).active.iter_rows(values_only=True))
    hi = next(i for i, r in enumerate(rows) if r and r[0] == "Name")
    head = [str(h) for h in rows[hi]]
    ix = {k: head.index(k) for k in ("Name", "Ticker", "Weight")}
    return "", [{"ticker": str(r[ix["Ticker"]]).replace(".", "-"), "name": str(r[ix["Name"]]).title(), "weight": num(r[ix["Weight"]])}
                for r in rows[hi + 1:] if r and r[ix["Ticker"]] and num(r[ix["Weight"]])]


def qqq():
    j = json.loads(get("https://dng-api.invesco.com/cache/v1/accounts/en_US/shareclasses/QQQ/holdings/fund?idType=ticker&interval=daily&productType=ETF"))
    return str(j.get("effectiveDate") or ""), [{"ticker": str(h["ticker"]).replace(".", "-"), "name": str(h.get("issuerName") or "").title(),
                                                 "weight": num(h.get("percentageOfTotalNetAssets"))} for h in j.get("holdings", []) if h.get("ticker")]


def soletf_space():
    page = get("https://www.soletf.com/ko/fund/etf/211110?tabIndex=3", 60).decode("utf-8", "replace")
    items = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", page, re.S):
        cells = [html.unescape(re.sub(r"<[^>]+>", "", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        cells = [c for c in cells if c]
        if len(cells) < 4 or not cells[-1].endswith("%") or "현금" in cells[-4]:
            continue
        nm, w = cells[-4], num(cells[-1])
        tk = next((t for k, t in NAME2TICKER.items() if k in nm.lower()), None)
        if tk and w:
            items.append({"ticker": tk, "name": nm, "weight": w})
    return "", items


FALLBACK = {"sp": ("SPY 보유종목 공시", spy), "ndx": ("QQQ 보유종목 공시", qqq), "space": ("신한자산운용 구성종목", soletf_space)}


def main():
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    today = dt.datetime.now(KST).strftime("%Y-%m-%d")
    out = {"generated_at_kst": dt.datetime.now(KST).strftime("%Y-%m-%d %H:%M"), "etfs": dict(old.get("etfs", {})), "errors": []}
    cache = {}
    failed = [x for x in ETFS if not one(*x, out, cache, today)]
    if failed:  # 실패한 ETF만 잠깐 쉬고 한 번 더 (승인 30번)
        print(f"실패 {len(failed)}개 → 30초 쉬고 한 번 더")
        time.sleep(30)
        for code, name, g in failed:
            before = len(out["errors"])
            if one(code, name, g, out, cache, today):
                out["errors"] = [e for e in out["errors"] if not e.startswith(code + " ")]
                print(f"  {code} 두 번째에 받음")
            else:
                del out["errors"][before:]  # 같은 오류 두 번 적지 않아요
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"ETF {len(out['etfs'])}개, 오류 {len(out['errors'])}개")
    for e in out["errors"]:
        print(" -", e)
    for c, v in out["etfs"].items():
        print(c, v["src"], v["n_total"], v["top_weight"], [(i["ticker"], i["weight"]) for i in v["top"][:4]])


def one(code, name, g, out, cache, today):
    """ETF 하나의 구성종목을 받아 out 에 넣어요. 못 받으면 이전 값을 두고 False."""
    G = GROUPS[g]
    src, asof, items = "", "", []
    funetf.other, funetf.asia, funetf.isin_rest = [], [], []
    if G["kind"] == "bond":  # 채권형은 회사가 아니라 국채를 담아서, 같은 지수 미국 ETF(proxy)만 써요
        out["etfs"][code] = {"kind": "bond", "group": g, "name": name, "index": G["name"], "proxy": G["proxy"], "asof": f"{today} 확인",
                             "n_total": 0, "top": [], "top_weight": 0, "cash_weight": 0, "src": f"채권형 · {G['proxy']}(같은 지수 미국 ETF)로 계산"}
        return True
    try:
        asof, items = funetf(code)
        src = "FunETF 구성종목 공시"
        time.sleep(1.5)
    except Exception as e:  # noqa: BLE001
        out["errors"].append(f"{code} FunETF: {type(e).__name__}: {str(e)[:120]}")
    if len(items) < 5 and g in FALLBACK:
        try:
            if g not in cache:
                cache[g] = FALLBACK[g][1]()
            asof, items = cache[g]
            src = FALLBACK[g][0]
        except Exception as e:  # noqa: BLE001
            out["errors"].append(f"{code} 대체 출처: {type(e).__name__}: {str(e)[:120]}")
    if len(items) + len(funetf.asia) < 5:
        out["errors"].append(f"{code} {name}: 구성종목을 못 받아서 이전 값을 그대로 둬요")
        return False
    merged = {}
    for i in items:
        if i["weight"]:
            if i["ticker"] in merged:
                merged[i["ticker"]]["weight"] += i["weight"]
            else:
                merged[i["ticker"]] = dict(i)
    items = sorted(merged.values(), key=lambda i: -i["weight"])
    asia_w = round(sum(w for _, w in funetf.asia), 2)
    isin_w = round(sum(w for _, w in funetf.isin_rest), 2)
    top = items[:TOP_INDEX] if G["kind"] == "index" else items[:TOP_PDF]
    tw = sum(i["weight"] for i in items)
    out["etfs"][code] = {"kind": G["kind"], "group": g, "name": name, "index": G["name"], "proxy": G["proxy"],
                         "asof": asof or f"{today} 받음", "n_total": len(items) + len(funetf.isin_rest),
                         "top": [{"ticker": i["ticker"], "name": i["name"], "ko": i.get("ko", ""), "weight": round(i["weight"], 3)} for i in top],
                         "top_weight": round(sum(i["weight"] for i in top), 2), "cash_weight": round(max(0.0, 100 - tw - asia_w - isin_w), 2) if G["kind"] == "pdf" else 0,
                         "asia_weight": asia_w if G["kind"] == "pdf" else 0, "asia": [a[0] for a in funetf.asia[:12]] if G["kind"] == "pdf" else [],
                         "rest_weight": round(max(0.0, tw - sum(i["weight"] for i in top)) + isin_w, 2) if G["kind"] == "pdf" else 0,
                         "rest_extra": [a[0] for a in funetf.isin_rest[:12]] if G["kind"] == "pdf" else [],
                         "src": src, "other": funetf.other[:15]}
    return True


if __name__ == "__main__":
    main()
