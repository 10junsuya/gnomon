"""data/*.json 검사 (Quill이 고친 뒤, 그리고 GitHub에서 자동으로 돌아요).

python3 scripts/check_data.py          → 검사만
python3 scripts/check_data.py --embed  → 검사 통과 시 index.html 안의 데이터 블록을 data/*.json 으로 갱신

문제가 있으면 무엇이 왜 틀렸는지 한국어로 출력하고 실패(1)로 끝나요.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / "index.html"
FILES = {"d-events": "data/events.json", "d-missions": "data/missions.json", "d-money": "data/money.json",
         "d-holdings": "data/holdings.json", "d-live": "data/live.json", "d-macro": "data/macro.json", "d-etfs": "data/etfs.json",
         "d-earnings": "data/earnings.json", "d-track": "data/track.json",
         "d-companies": "data/companies.json", "d-views": "data/views.json",
         "d-dist": "data/dist.json", "d-aimap": "data/aimap.json"}
OPTIONAL = {"d-holdings", "d-live", "d-macro", "d-track", "d-views", "d-dist"}  # 자동 수집 파일: 없으면 빈 값으로 넣어요
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
URL = re.compile(r"^https://[^\s<>\"]+$")  # 보안: https 링크만
TYPES = {"earn", "launch", "land", "event"}
errors = []


def err(where, msg):
    errors.append(f"[{where}] {msg}")


def tickers():
    s = APP.read_text(encoding="utf-8")
    i = s.find("const STOCKS = {")
    j = s.find("\n};", i)
    return set(re.findall(r"\b([A-Z]{1,6})\s*:\s*\[", s[i:j]))


def check_analysis(where, a):
    """발표 분석 블록: lead(핵심 한 줄) + points(짧은 줄 3개까지) + items(매체 해석, 5개까지). 읽기 쉽게 짧게."""
    if not isinstance(a, dict):
        err(where, "분석 블록은 {lead, points, items, asof} 모양이어야 해요.")
        return
    lead = str(a.get("lead", ""))
    if not re.search(r"[가-힣]", lead) or len(lead) > 70:
        err(where, "lead(핵심 한 줄)는 한국어 70자 이하로 꼭 써요.")
    pts = a.get("points") or []
    if not isinstance(pts, list) or len(pts) > 3:
        err(where, "points 는 3줄까지예요.")
        pts = []
    for n, b in enumerate(pts):
        if isinstance(b, list):  # [이름표, 글] — 이름표는 6자 안팎
            if len(b) != 2 or len(str(b[0])) > 8:
                err(f"{where}.points[{n}]", "[이름표(8자 이하), 글] 모양이어야 해요.")
            b = b[1] if len(b) == 2 else ""
        if not re.search(r"[가-힣]", str(b)) or len(str(b)) > 80:
            err(f"{where}.points[{n}]", "한 줄은 한국어 80자 이하로 짧게 써요.")
    if a.get("asof") and not DATE.match(str(a["asof"])):
        err(where, "asof 는 YYYY-MM-DD 로 써요.")
    items = a.get("items") or []
    if len(items) > 5:
        err(where, "매체 해석은 5줄까지만 써요.")
    for n, x in enumerate(items):
        w = f"{where}.items[{n}]"
        t = str(x.get("t", ""))
        if not re.search(r"[가-힣]", t) or len(t) > 90:
            err(w, "한국어 한 줄(90자 이하)로 써야 해요. 영어 제목을 그대로 넣지 않아요.")
        if not str(x.get("src", "")).strip():
            err(w, "매체 이름(src)이 비어 있어요.")
        if not URL.match(str(x.get("url", ""))):
            err(w, "링크(url)는 https 로 시작해야 해요.")
        if not DATE.match(str(x.get("d", ""))):
            err(w, "날짜(d)는 YYYY-MM-DD 로 써요.")
        if x.get("tag") not in ("보도", "공식"):
            err(w, "tag는 '보도' 또는 '공식'이에요.")


def check_views(d, events=None):
    """매크로 지표 발표 분석 (data/views.json) + 실적·회사 이벤트 카드의 card.views"""
    for k, v in ((d or {}).get("ind") or {}).items():
        if v.get("rel") and not DATE.match(str(v["rel"])[:10]):
            err(f"views.{k}", "rel(발표일)은 YYYY-MM-DD 로 시작해야 해요.")
        check_analysis(f"views.{k}", v)
    for e in events or []:
        c = e.get("card") or {}
        if "views" in c:
            check_analysis(f"events.{e.get('t')}.{e.get('d')}.card.views", c["views"])


def check_src(where, src):
    if not isinstance(src, list) or not src:
        err(where, "출처(src)가 비어 있어요. 공식 출처 링크가 꼭 있어야 해요.")
        return
    for x in src:
        if not (isinstance(x, list) and len(x) == 2 and isinstance(x[0], str) and URL.match(str(x[1]))):
            err(where, f"출처 형식이 틀렸어요: {x!r} (예: [\"이름\", \"https://...\"])")


EV_LEGACY = {ln.strip() for ln in (ROOT / "ops" / "events_nosrc.txt").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")} if (ROOT / "ops" / "events_nosrc.txt").exists() else set()


def check_events(ev, known):
    if not isinstance(ev, list):
        return err("events", "목록([ ])이어야 해요.")
    seen = set()
    for n, e in enumerate(ev):
        w = f"events #{n} {e.get('t')}:{e.get('d')}" if isinstance(e, dict) else f"events #{n}"
        if not isinstance(e, dict):
            err(w, "항목이 객체({ })가 아니에요.")
            continue
        if not DATE.match(str(e.get("d", ""))):
            err(w, "날짜(d)는 YYYY-MM-DD 형식이어야 해요.")
        if e.get("t") not in known:
            err(w, f"티커(t) {e.get('t')!r} 가 앱 종목 목록(STOCKS)에 없어요.")
        if e.get("type") not in TYPES:
            err(w, f"종류(type)는 {sorted(TYPES)} 중 하나여야 해요.")
        if not str(e.get("title", "")).strip():
            err(w, "제목(title)이 비어 있어요.")
        key = (e.get("t"), e.get("d"))
        if key in seen:
            err(w, "같은 회사·날짜 일정이 두 번 들어 있어요.")
        seen.add(key)
        # 대표 승인 44번(2026-11-23): 일정마다 공식 출처 칸 src. 그 전부터 있던 일정은 ops/events_nosrc.txt 에 있으면 봐줘요
        if e.get("src") is not None or f"{e.get('t')}:{e.get('d')}" not in EV_LEGACY:
            check_src(w + " 일정 출처", e.get("src"))
        c = e.get("card")
        if c:
            if c.get("real") and not DATE.match(str(c.get("asof", ""))):
                err(w, "실제 결과 카드(real)는 기준일(asof)이 있어야 해요.")
            check_src(w, c.get("src"))
            for t in c.get("tiles", []):
                if not (isinstance(t, list) and len(t) >= 3):
                    err(w, f"타일 형식이 틀렸어요: {t!r}")


def check_missions(ms, ev, art_counts):
    keys = {f"{e.get('t')}:{e.get('d')}" for e in ev if isinstance(e, dict)}
    for k, m in ms.items():
        w = f"missions {k}"
        if k not in keys:
            err(w, "events.json 에 같은 회사·날짜 일정이 없어요.")
        if not isinstance(m.get("ok"), bool):
            err(w, "ok 는 true(완료) 또는 false(예정)여야 해요.")
        steps = m.get("steps")
        if not (isinstance(steps, list) and steps and all(isinstance(s, list) and len(s) == 3 for s in steps)):
            err(w, "단계(steps)는 [시각, 제목, 설명] 목록이어야 해요.")
        elif k in art_counts and art_counts[k] and art_counts[k] != len(steps):
            err(w, f"단계 수({len(steps)})가 그림 수({art_counts[k]})와 달라요. 단계를 늘리거나 줄이면 그림도 같이 바꿔야 해서 사람 승인이 필요해요.")
        if len(m.get("tags", [])) not in (0, len(steps or [])):
            err(w, "tags 수가 단계 수와 달라요.")


def check_money(mo, known):
    for t, m in mo.items():
        w = f"money {t}"
        if t not in known:
            err(w, "앱 종목 목록에 없는 티커예요.")
        if not str(m.get("p", "")).strip():
            err(w, "기간(p)이 비어 있어요.")
        segs = m.get("segs")
        if not (isinstance(segs, list) and segs):
            err(w, "사업(segs)이 비어 있어요.")
            continue
        for s in segs:
            if not (isinstance(s, list) and len(s) >= 2 and isinstance(s[0], str) and isinstance(s[1], (int, float)) and s[1] > 0):
                err(w, f"사업 형식이 틀렸어요: {s!r} (예: [\"데이터센터\", 89000, \"설명\"])")
        if m.get("pct") and abs(sum(s[1] for s in segs if isinstance(s, list) and len(s) > 1 and isinstance(s[1], (int, float))) - 100) > 2:
            err(w, "비율만 쓰는 경우(pct) 합이 100% 근처여야 해요.")
        if not str(m.get("note", "")).strip():
            err(w, "한 줄 설명(note)이 비어 있어요.")
        check_src(w, m.get("src"))


CURS = {"usd", "eur", "cad", "krw", "twd", "cny"}


def check_earnings(eq, known):
    """실적 카드(data/earnings.json): 금액은 백만 단위, 통화는 CURS 중 하나."""
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    for t, q in eq.items():
        w = f"earnings {t}"
        if t not in known:
            err(w, "앱 종목 목록에 없는 티커예요.")
        if not str(q.get("p", "")).strip():
            err(w, "기간(p)이 비어 있어요.")
        rows = q.get("rows")
        if not (isinstance(rows, list) and rows and all(isinstance(r, list) and len(r) == 2 for r in rows)):
            err(w, "rows 는 [[\"이름\", \"값\"], ...] 형식이어야 해요.")
        check_src(w, q.get("src"))
        c = q.get("chart")
        if c is None:
            continue
        if c.get("cur") not in CURS:
            err(w, f"통화(cur)는 {sorted(CURS)} 중 하나여야 해요.")
        now = c.get("now")
        if not (isinstance(now, list) and len(now) == 2 and num(now[1]) and now[1] > 0):
            err(w, "now 는 [\"7~9월\", 금액] 형식이어야 해요.")
        if "prev" in c and not (isinstance(c["prev"], list) and len(c["prev"]) == 2 and num(c["prev"][1]) and c["prev"][1] > 0):
            err(w, "prev 는 [\"1년 전\", 금액] 형식이어야 해요 (모르면 prev 를 빼요).")
        if c.get("est") is not None and not (num(c["est"]) and c["est"] > 0):
            err(w, "est 는 숫자나 null 이어야 해요.")
        n = c.get("next")
        if not isinstance(n, dict) or not str(n.get("when", "")).strip():
            err(w, "next.when(다음 발표)이 비어 있어요.")
            continue
        g = n.get("guide")
        if g is not None and not (isinstance(g, list) and len(g) == 2 and all(num(x) for x in g) and g[0] <= g[1]):
            err(w, "next.guide 는 [낮은 값, 높은 값] 이어야 해요.")
        if n.get("cons") is not None and not num(n["cons"]):
            err(w, "next.cons 는 숫자나 null 이어야 해요.")


# 특정 회사 제품을 그린 그림: 다른 회사 제품에 쓰면 틀린 그림이 나와요 (예: 스타십 자리에 뉴트론)
BRANDED_ART = {"electron": {"RKLB"}, "neutron": {"RKLB"}, "haste": {"RKLB"}, "alpha": {"FLY"}, "blueghost": {"FLY"},
               "novac": {"LUNR"}, "bluebird": {"ASTS"}, "dove": {"PL"}, "starship": {"SPCX"}, "iphone": {"AAPL", "VZ", "GLW"},
               # 실제 제품 모양 그림 (2026-11 대표 요청으로 추가)
               "f35": {"LMT", "NOC"}, "f22": {"LMT"}, "f16": {"LMT"}, "c130": {"LMT"}, "uh60": {"LMT"}, "ch53k": {"LMT"},
               "pac3": {"LMT"}, "thaad": {"LMT"}, "prsm": {"LMT"}, "himars": {"LMT"}, "jassm": {"LMT"}, "javelin": {"LMT"},
               "trident": {"LMT"}, "orion": {"LMT"}, "destroyer": {"LMT", "RTX"},
               "tomahawk": {"RTX"}, "sm6": {"RTX"}, "sm3": {"RTX"}, "amraam": {"RTX"}, "patriot": {"RTX"}, "nasams": {"RTX"},
               "ltamds": {"RTX"}, "e2d": {"NOC"}, "b21": {"NOC"}, "triton": {"NOC"}, "icbm": {"NOC"}, "aargm": {"NOC"},
               "falcon9": {"SPCX"}, "falconheavy": {"SPCX"}, "dragon": {"SPCX"}, "hls": {"SPCX"},
               "turbofan": {"GE", "RTX"}, "jeteng": {"GE", "RTX"}, "davinci": {"ISRG"}, "oklo": {"OKLO"}, "nuscale": {"SMR"}, "joby": {"JOBY"}, "vertiport": {"JOBY"}, "midnight": {"ACHR"},
               "alia": {"BETA"}, "alia250": {"BETA"}, "xe100": {"XE"}}


def check_product_art(comp):
    for t, p in (comp.get("products") or {}).items():
        for cat in p.get("cats", []):
            for it in cat.get("items", []):
                a = it.get("art")
                if a in BRANDED_ART and t not in BRANDED_ART[a]:
                    err(f"products {t}", f"'{a}' 그림은 {sorted(BRANDED_ART[a])} 제품 전용이에요. 이 회사 제품에 맞는 그림을 써 주세요.")


def check_companies(comp, known):
    """회사 정보: 앱 종목만, 소개는 tag·cat·one 필수, 최근 소식은 날짜·제목·출처 필수"""
    for sec in ("co", "products", "px", "chain", "news"):
        if not isinstance(comp.get(sec, {}), dict):
            err("companies", f"{sec} 는 {{티커: ...}} 모양이어야 해요.")
            return
    for t, c in comp.get("co", {}).items():
        w = f"companies.co {t}"
        if t not in known:
            err(w, "앱에 없는 종목이에요(index.html STOCKS 에 먼저 있어야 해요).")
        for k in ("tag", "cat", "one"):
            if not str(c.get(k, "")).strip():
                err(w, f"{k} 가 비어 있어요.")
    for x in comp.get("market", []) if isinstance(comp.get("market", []), list) else []:
        if not (isinstance(x, dict) and DATE.match(str(x.get("d", ""))) and str(x.get("t", "")).strip() and x.get("kind") in ("공식", "보도")):
            err("companies.market", "d·t·kind('공식'/'보도')가 있어야 해요.")
        else:
            check_src("companies.market", x.get("src"))
    for t, xs in comp.get("news", {}).items():
        w = f"companies.news {t}"
        if t not in known:
            err(w, "앱에 없는 종목이에요.")
        if not isinstance(xs, list):
            err(w, "목록이어야 해요.")
            continue
        for x in xs:
            if not (isinstance(x, dict) and DATE.match(str(x.get("d", ""))) and str(x.get("t", "")).strip()):
                err(w, "d(YYYY-MM-DD)·t(한국어 한 줄)가 있어야 해요.")
                continue
            if x.get("kind") not in ("공식", "보도"):
                err(w, "kind 는 '공식' 또는 '보도'예요.")
            check_src(w, x.get("src"))


DANGER = re.compile(r"<\s*/?\s*(script|iframe|img|svg|object|embed|link|style|meta|form|input|a)\b|\bon[a-z]+\s*=|javascript:|vbscript:|data:text/html|srcdoc\s*=", re.I)


def check_safety(name, obj, path="", seen=None):
    """보안: 화면에 들어갈 데이터에 코드(HTML 태그·스크립트·위험 링크)가 숨어 있지 않은지 봐요."""
    if seen is None:
        seen = [0]
    if seen[0] > 20:
        return
    if isinstance(obj, str):
        if DANGER.search(obj):
            seen[0] += 1
            err(name, f"{path or '값'}에 화면 코드처럼 보이는 글자가 있어요 (보안상 넣을 수 없어요): {obj[:60]!r}")
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if DANGER.search(str(k)):
                err(name, f"이름(키)에 화면 코드처럼 보이는 글자가 있어요: {str(k)[:40]!r}")
            check_safety(name, v, f"{path}.{k}" if path else str(k), seen)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            check_safety(name, v, f"{path}[{i}]", seen)


HANGUL = re.compile(r"[가-힣]")


def check_directives(data):
    """대표 지시 모음(ops/DIRECTIVES.md) 중 기계로 잡을 수 있는 것."""
    comp = data.get("d-companies") or {}
    # 지시 2: 영어 기사 제목을 그대로 넣지 않아요 — 소식 한 줄은 한국어여야 해요
    items = [(f"companies.news.{t}", x) for t, xs in (comp.get("news") or {}).items() for x in xs] + \
            [("companies.market", x) for x in (comp.get("market") or [])]
    for w, x in items:
        t = str(x.get("t", ""))
        letters = [c for c in t if c.isalpha()]
        if letters and sum(1 for c in letters if HANGUL.match(c)) / len(letters) < 0.4:
            err(w, f"소식이 영어로 보여요(지시 모음 2번: 한국어 한 줄로 새로 써요): {t[:60]!r}")
    # 지시 12: 가짜 자리 채움 문구를 남기지 않아요
    app = APP.read_text(encoding="utf-8")
    # 합치기(merge) 충돌 표시가 남은 채로 올라가면 앱이 깨져요
    if re.search(r"^(<<<<<<<|>>>>>>>|=======$)", app, flags=re.M):
        err("index.html", "합치기 충돌 표시(<<<<<<< / >>>>>>>)가 남아 있어요. 충돌을 풀고 다시 올려 주세요.")
    code = re.sub(r'<script type="application/json" id="[^"]+">.*?</script>', "", app, flags=re.S)
    for bad in ("[예시]", "요약이 여기에 들어가요", "lorem ipsum"):
        if bad in code:
            err("index.html", f"자리 채움 문구가 남아 있어요(지시 모음 12번): {bad!r}")


def art_frame_counts():
    s = APP.read_text(encoding="utf-8")
    i = s.find("const MISSION_ART = ")
    if i < 0:
        return {}
    j = s.find(";\n", i)
    try:
        art = json.loads(s[i + len("const MISSION_ART = "):j])
    except ValueError:
        return {}
    return {k: len(v) for k, v in art.items()}


def block(id_, obj):
    txt = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{id_}">{txt}</script>'


def check_dist(d):
    """분배금(data/dist.json, SEIBro 자동 수집): 날짜·금액 모양만 본다."""
    if not d:
        return
    for code, v in (d.get("etfs") or {}).items():
        for h in v.get("hist", []):
            if not (isinstance(h, list) and len(h) == 4 and isinstance(h[0], str) and DATE.match(h[0])):
                err("data/dist.json", f"{code}: 기록 모양이 잘못됐어요 {h}"); continue
            if h[1] is not None and not (isinstance(h[1], str) and DATE.match(h[1]) and h[1] >= h[0]):
                err("data/dist.json", f"{code}: 지급일({h[1]})이 기준일({h[0]})보다 빨라요")
            if not isinstance(h[2], (int, float)) or h[2] < 0 or h[2] > 100000:
                err("data/dist.json", f"{code}: 주당분배금({h[2]})이 이상해요")
            if h[3] not in ("이익", "청산"):
                err("data/dist.json", f"{code}: 구분({h[3]})이 이상해요")


EVS = ("회사 발표", "공시", "정부 문서", "보도")


def _aimap_projects(name, P, keys):
    seen = set()
    for p in P:
        pid = p.get("id")
        if not pid or pid in seen:
            err("data/aimap.json", f"{name} 프로젝트 id가 없거나 겹쳐요: {pid}")
        seen.add(pid)
        for f in ("r", "n", "d", "st", "chk"):
            if not p.get(f):
                err("data/aimap.json", f"{pid}: {f} 칸이 비어 있어요")
        if p.get("chk") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p["chk"]):
            err("data/aimap.json", f"{pid}: 확인일 모양이 이상해요")
        L = p.get("L", {})
        if not L:
            err("data/aimap.json", f"{pid}: 연결된 층이 없어요")
        for k, v in L.items():
            if k not in keys:
                err("data/aimap.json", f"{pid}: 모르는 층 {k}")
            if v.get("ev") not in EVS:
                err("data/aimap.json", f"{pid}/{k}: 근거 꼬리표({v.get('ev')})는 {'·'.join(EVS)} 중 하나여야 해요")
            if not v.get("t"):
                err("data/aimap.json", f"{pid}/{k}: 설명이 비어 있어요")
            if "수혜" in v.get("t", ""):
                err("data/aimap.json", f"{pid}/{k}: '수혜' 표현은 쓰지 않아요")
        src = p.get("src", [])
        if not src:
            err("data/aimap.json", f"{pid}: 출처가 없어요")
        for s in src:
            if len(s) != 2 or not str(s[1]).startswith("https://"):
                err("data/aimap.json", f"{pid}: 출처 링크는 https 로 시작해야 해요")


def _aimap_map(name, ai):
    co = ai.get("co", {})
    if not co or not ai.get("rows") or not ai.get("e"):
        err("data/aimap.json", f"{name} 지도에 층·회사·관계가 있어야 해요")
        return
    placed = set()
    for r in ai["rows"]:
        for g in r.get("g", []):
            for c in g.get("co", []):
                if c not in co:
                    err("data/aimap.json", f"{name} 지도 {r.get('n')}: 회사 정보가 없는 이름 {c}")
                if c in placed:
                    err("data/aimap.json", f"{name} 지도: {c}가 두 칸에 들어 있어요")
                placed.add(c)
    for c in co:
        if c not in placed:
            err("data/aimap.json", f"{name} 지도: {c}가 어느 칸에도 없어요")
    for i, e in enumerate(ai["e"]):
        tag = f"{name} 관계 {i + 1} ({e.get('a')}→{e.get('b')})"
        if e.get("a") not in co or e.get("b") not in co or e.get("a") == e.get("b"):
            err("data/aimap.json", f"{tag}: 양쪽 회사가 지도에 있어야 해요")
        if e.get("k") not in ("공급", "클라우드", "건설", "전력", "투자", "협력"):
            err("data/aimap.json", f"{tag}: 관계 종류({e.get('k')})가 이상해요")
        if e.get("ev") not in EVS:
            err("data/aimap.json", f"{tag}: 근거 꼬리표가 이상해요")
        if not e.get("t") or "수혜" in e.get("t", ""):
            err("data/aimap.json", f"{tag}: 설명이 비었거나 '수혜' 표현이 있어요")
        for f in ("chk", "add"):
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(e.get(f, ""))):
                err("data/aimap.json", f"{tag}: {f}(확인일·추가일) 모양이 이상해요")
        s2 = e.get("src") or []
        if len(s2) != 2 or not str(s2[1]).startswith("https://"):
            err("data/aimap.json", f"{tag}: 출처 링크는 https 로 시작해야 해요")


def check_aimap(d):
    """Aleph 산업 지도(옛 A 화면, data/aimap.json): 층 이름, 근거 꼬리표, 출처 링크, 확인일 모양을 본다.
    AI 는 맨 위 projects·layers 와 ai, 다른 산업(예: semi)은 그 키 안에 rows·co·e·layers·projects."""
    if not d:
        err("data/aimap.json", "비어 있어요")
        return
    keys = [x[0] for x in d.get("layers", [])]
    if len(keys) != 8 or len(set(keys)) != 8:
        err("data/aimap.json", "층(layers)은 서로 다른 8개여야 해요")
    _aimap_projects("AI", d.get("projects", []), keys)
    _aimap_map("AI", d.get("ai") or {})
    for k, n, _d, st in d.get("industries", []):
        if k == "ai":
            continue
        if st == "open" and not d.get(k):
            err("data/aimap.json", f"{n}: 열림인데 지도 데이터가 없어요")
        D = d.get(k)
        if D:
            lk = [x[0] for x in D.get("layers", [])]
            if len(lk) != len(set(lk)) or not lk:
                err("data/aimap.json", f"{n}: 층(layers) 이름이 비었거나 겹쳐요")
            _aimap_projects(n, D.get("projects", []), lk)
            _aimap_map(n, D)


def main():
    embed = "--embed" in sys.argv
    data = {}
    for id_, f in FILES.items():
        try:
            data[id_] = json.loads((ROOT / f).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            if id_ in OPTIONAL:
                data[id_] = {}
            else:
                err(f, f"JSON을 읽을 수 없어요: {e}")
    if not errors:
        known = tickers()
        check_events(data["d-events"], known)
        check_missions(data["d-missions"], data["d-events"], art_frame_counts())
        check_money(data["d-money"], known)
        check_earnings(data["d-earnings"], known)
        check_product_art(data["d-companies"])
        check_companies(data["d-companies"], known)
        check_views(data["d-views"], data["d-events"])
        check_dist(data["d-dist"])
        check_aimap(data["d-aimap"])
        for id_, f in FILES.items():
            check_safety(f, data[id_])
        check_directives(data)
    if errors:
        print("데이터 검사 실패:")
        print("\n".join(" - " + e for e in errors))
        return 1
    s = APP.read_text(encoding="utf-8")
    new = s
    for id_ in FILES:
        if f'id="{id_}"' not in new:
            new = new.replace('<!-- DATA:END -->', block(id_, data[id_]) + '\n<!-- DATA:END -->', 1)
            continue
        new = re.sub(rf'<script type="application/json" id="{id_}">.*?</script>', lambda _m, i=id_: block(i, data[i]), new, count=1, flags=re.S)
    if new != s:
        if embed:
            APP.write_text(new, encoding="utf-8")
            print("데이터 검사 통과 · index.html 데이터 블록을 갱신했어요.")
        else:
            print("데이터 검사는 통과했지만 index.html 안의 데이터가 data/*.json 과 달라요.")
            print("  → python3 scripts/check_data.py --embed 를 실행한 뒤 함께 커밋하세요.")
            return 1
    else:
        print("데이터 검사 통과 · index.html 과 일치해요.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
