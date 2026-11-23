"""Argus — 노몬 경비 프로그램 (AI 아님, GitHub에서 10분마다)

보는 것
1. 실시간 서버(gnomon-live)가 살아 있는지
2. 자동 수집 자료가 너무 오래되지 않았는지 (평일 기준)
3. 미국장이 열려 있을 때: 같은 지수 미국 ETF(SPY·QQQ·SOXQ·SMH·SCHD)와 watchlist 종목이 크게 움직였는지
4. 앱 데이터 검사(check_data.py)가 통과하는지
5. 보안 감시: 서버 방어가 그대로 켜져 있는지(실제로 찔러 봐요), 응답이 느려지지 않았는지,
   저장소에 키·개인정보가 올라오지 않았는지, 앱·서버의 보안 장치가 지워지지 않았는지, 긴급 정지 상태인지
새 알림만 ops/board/argus.md 에 적고(같은 알림은 6시간에 한 번), 상태는 ops/argus/state.json 에 남겨요.
앱 숫자가 틀릴 수 있는 '긴급'이면 실행을 실패로 끝내서 GitHub 알림 메일이 가게 해요.
"""
import re
import datetime as dt, json, subprocess, sys, urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
KST, NY = ZoneInfo("Asia/Seoul"), ZoneInfo("America/New_York")
LIVE = "https://gnomon-live.leejoonsoo85.workers.dev"
STATE, BOARD = ROOT / "ops/argus/state.json", ROOT / "ops/board/argus.md"
now = dt.datetime.now(KST)
sys.path.insert(0, str(ROOT / "scripts"))
from etf_list import GROUPS  # noqa: E402


def get(u):
    with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "gnomon-argus"}), timeout=20) as r:
        return json.loads(r.read().decode())


def age_h(ts):
    try:
        return (now - dt.datetime.strptime(ts[:16], "%Y-%m-%d %H:%M").replace(tzinfo=KST)).total_seconds() / 3600
    except (TypeError, ValueError):
        return 999


def biz_age_h(ts):
    """토·일(한국 시간)을 뺀 자료 나이(시간). 대표 승인 46번(2026-11-23): 월요일 새벽에 금요일 자료를 '멈춤'으로 알리던 문제."""
    try:
        t0 = dt.datetime.strptime(ts[:16], "%Y-%m-%d %H:%M").replace(tzinfo=KST)
    except (TypeError, ValueError):
        return 999
    h, t = 0.0, t0
    while t < now:
        nxt = min(now, dt.datetime.combine(t.date() + dt.timedelta(days=1), dt.time(), KST))
        if t.weekday() < 5:
            h += (nxt - t).total_seconds() / 3600
        t = nxt
    return h


alerts = []  # (key, 급함 여부, 제목, 내용)
# 1. 서버
try:
    h = get(LIVE + "/health")
    if not h.get("ok", True):
        alerts.append(("server", True, "실시간 서버 이상", json.dumps(h, ensure_ascii=False)[:200]))
except Exception as e:  # noqa: BLE001
    alerts.append(("server", True, "실시간 서버 응답 없음", f"{type(e).__name__}: {str(e)[:120]}"))

# 2. 자료 나이 (평일만, 넉넉하게)
if now.weekday() < 5:
    for f, lim in (("live.json", 30), ("holdings.json", 54), ("macro.json", 30)):
        try:
            a = biz_age_h(json.loads((ROOT / "data" / f).read_text(encoding="utf-8")).get("generated_at_kst"))
        except (OSError, ValueError):
            a = 999
        if a > lim:
            alerts.append((f"stale:{f}", f == "live.json", f"자동 수집이 멈춘 듯해요: {f}", f"마지막으로 받은 지 주말 빼고 {a:.0f}시간 (기준 {lim}시간)"))
    # 분배금(SEIBro, 평일 저녁 1번): 주말을 넘겨도 80시간이면 충분. 실패가 많으면 사이트 구조가 바뀐 것일 수 있어요
    try:
        _d = json.loads((ROOT / "data/dist.json").read_text(encoding="utf-8"))
        _a = age_h(_d.get("updated_kst"))
        if _a > 80:
            alerts.append(("stale:dist.json", False, "분배금 수집이 멈춘 듯해요: dist.json", f"마지막으로 받은 지 {_a:.0f}시간 (기준 80시간) · SEIBro 화면이 바뀌었는지 확인"))
        if (_d.get("fail") or 0) >= 10:
            alerts.append(("dist:fail", False, "분배금 수집 실패가 많아요", f"59개 중 {_d.get('fail')}개 실패 · 이전 기록을 그대로 쓰는 중"))
    except (OSError, ValueError):
        pass
    # Aleph 산업 지도(사람이 넣는 자료): 관계 확인일이 45일 넘으면 다시 확인할 때예요 (2026-11-19 대표 승인)
    try:
        _m = json.loads((ROOT / "data/aimap.json").read_text(encoding="utf-8"))
        _old = [e for _k in ("ai", "semi", "space", "power") for e in (_m.get(_k) or {}).get("e", []) if (dt.date.today() - dt.date.fromisoformat(e.get("chk", "2000-01-01"))).days > 45]
        if _old:
            alerts.append(("stale:aimap", False, f"Aleph 산업 지도 관계 {len(_old)}개 확인이 오래됐어요", "확인일이 45일을 넘었어요 · Wren이 바뀐 소식을 찾고 Vernon이 근거를 다시 확인해 주세요"))
    except (OSError, ValueError):
        pass

# 3. 큰 움직임 (미국 정규장 + 장 마감 후 2시간)
ny = dt.datetime.now(NY)
wl = json.loads((ROOT / "ops/watchlist.json").read_text(encoding="utf-8"))
if ny.weekday() < 5 and (9 * 60 + 30) <= ny.hour * 60 + ny.minute <= 18 * 60:
    proxies = sorted({g["proxy"] for g in GROUPS.values() if g.get("proxy")})
    items = [i for i in wl.get("items", []) if i.get("until", "9999") >= now.strftime("%Y-%m-%d")]
    syms = proxies + [i["t"] for i in items if i["t"] not in proxies]
    try:
        q = get(LIVE + "/quote?s=" + ",".join(syms[:40]))
        q = q.get("quotes", q)
        for t in syms:
            v = q.get(t) or {}
            dp = v.get("change_pct")
            if dp is None:
                continue
            lim = next((i["move"] for i in items if i["t"] == t), None) or (wl["default"]["proxy_move"] if t in proxies else wl["default"]["stock_move"])
            if abs(dp) >= lim:
                why = next((i["why"] for i in items if i["t"] == t), "같은 지수 미국 ETF")
                alerts.append((f"move:{t}:{ny:%Y-%m-%d}", False, f"{t} {dp:+.1f}% (기준 ±{lim}%)", f"{why} · 가격 {v.get('price')} · {v.get('time')}"))
    except Exception as e:  # noqa: BLE001
        alerts.append(("quote", False, "시세를 못 받았어요", f"{type(e).__name__}: {str(e)[:120]}"))

# 4. 앱 데이터 검사
r = subprocess.run([sys.executable, str(ROOT / "scripts/check_data.py")], capture_output=True, text=True)
if r.returncode != 0:
    alerts.append(("check_data", True, "앱 데이터 검사 실패", (r.stdout + r.stderr).strip()[-400:]))

# 4-1. 구성종목 회사 정보 (지시 모음: 새 회사가 화면에서 빠지거나 소개 없이 들어오면 안 돼요)
try:
    _h = json.loads((ROOT / "data/holdings.json").read_text(encoding="utf-8")).get("etfs", {})
    _co = json.loads((ROOT / "data/companies.json").read_text(encoding="utf-8")).get("co", {})
    _norm = lambda t: str(t).replace("-", "").replace(".", "")
    _alias = {"GOOG": "GOOGL", "ECHO": "SATS"}  # 앱의 CO_ALIAS와 같아요 (같은 회사의 다른 티커)
    _need = sorted({_norm(x["ticker"]) for e in _h.values() for x in e.get("top", []) if x.get("ticker")} - set(_co) - set(_alias))
    if _need:
        alerts.append((f"noinfo:{','.join(_need)}", False, f"회사 소개 없는 구성종목 {len(_need)}곳",
                       f"{', '.join(_need)} — 구성종목에 새로 들어왔어요. Quill이 오늘 안에 data/companies.json·money.json을 공식 출처로 채워요 (RULES 6-1)"))
except (OSError, ValueError):
    pass

# 5. 보안 감시 (ops/SECURITY.md · ops/INCIDENT.md)
import time as _t, urllib.error  # noqa: E402


def probe(path, method="GET"):
    """실제 서버에 요청해 보고 (상태 코드, 헤더, 본문 앞부분, 걸린 초)를 돌려줘요."""
    t0 = _t.time()
    req = urllib.request.Request(LIVE + path, method=method, headers={"User-Agent": "gnomon-argus"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers), r.read(4000).decode("utf-8", "replace"), _t.time() - t0
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read(4000).decode("utf-8", "replace"), _t.time() - t0


sec = []


def _is_timeout(e):
    import socket  # noqa: PLC0415
    return isinstance(e, (TimeoutError, socket.timeout)) or (isinstance(e, urllib.error.URLError) and isinstance(getattr(e, "reason", None), (TimeoutError, socket.timeout))) or "timed out" in str(e)


def security_probes():
    st, hd, body, sec_t = probe("/health")
    hl = {k.lower(): v for k, v in hd.items()}
    if '"lockdown":true' in body.replace(" ", ""):
        alerts.append(("lockdown", True, "실시간 서버가 긴급 정지 상태예요", "ops/LOCKDOWN 또는 손으로 정지했어요. 사고 정리가 끝나면 0으로 되돌려요 (ops/INCIDENT.md)"))
    if hl.get("x-content-type-options") != "nosniff" or "default-src 'none'" not in hl.get("content-security-policy", ""):
        sec.append("보안 헤더가 사라졌어요")
    if '"keys"' in body:
        sec.append("상태 확인(/health)이 키 정보를 보여줘요")
    if sec_t > 8:
        alerts.append(("slow", False, "실시간 서버가 느려요", f"상태 확인에 {sec_t:.1f}초 (기준 8초). 공격이나 Cloudflare 장애일 수 있어요"))
    for path, method, want, what in (("/quote?s=NVDA", "POST", 405, "읽기 전용"), ("/quote?s=ZZZZZ", "GET", 400, "앱 종목만 받기"),
                                     ("/quote?s=NVDA&x=1", "GET", 400, "정해진 질문 칸만"), ("/admin", "GET", 404, "정해진 주소만")):
        code = probe(path, method)[0]
        if code != want and code != 503:  # 503은 긴급 정지 중
            sec.append(f"{what} 방어가 꺼졌어요 ({path} → {code}, 기대 {want})")
    st, _, body, _ = probe("/kis-check")
    # 값이 붙은 모양("nav": 123)만 경보. 칸 이름 목록(["nav", "last", ...])은 정상 응답이라 경보하지 않아요 (승인 12번)
    if re.search(r'"(last|stck_prpr|nav|base)"\s*:', body) or "access_token" in body:
        sec.append("/kis-check가 값이나 토큰을 보여줘요")


# 서버가 한 번 늦게 답한 것(시간 초과)은 보안 경보와 나눠요 (2026-11-18 승인 19번): 30초 뒤 한 번 더, 두 번 연속이면 긴급
for attempt in (1, 2):
    sec_try = len(sec)
    try:
        security_probes()
        break
    except Exception as e:  # noqa: BLE001
        del sec[sec_try:]
        if _is_timeout(e):
            if attempt == 1:
                _t.sleep(30)
                continue
            alerts.append(("slow:timeout2", True, "실시간 서버가 응답하지 않아요", "보안 점검 요청이 두 번 연속 시간 초과(20초)예요. Cloudflare 장애나 공격일 수 있어요 — 앱 숫자가 멈췄는지 확인해요"))
        else:
            sec.append(f"보안 점검 요청 실패: {type(e).__name__}")
        break
if attempt == 2 and not any(a[0] == "slow:timeout2" for a in alerts):
    alerts.append(("slow:timeout1", False, "실시간 서버가 느려요", "보안 점검 요청이 한 번 시간 초과됐다가 30초 뒤엔 정상이었어요(긴급 아님)"))
# 저장소에 키·개인정보
r = subprocess.run([sys.executable, str(ROOT / "scripts/secret_scan.py")], capture_output=True, text=True)
if r.returncode != 0:
    sec.append("저장소에 키·개인정보로 보이는 값이 있어요: " + " / ".join(l.strip() for l in r.stdout.splitlines() if l.startswith(" - "))[:300])
# 보안 장치가 코드에서 지워지지 않았는지
app = (ROOT / "index.html").read_text(encoding="utf-8")
wk = (ROOT / "worker/src/index.js").read_text(encoding="utf-8")
for ok_, what in (('http-equiv="Content-Security-Policy"' in app, "앱 보안 정책(CSP)"), ("function clean(" in app and "clean(JSON.parse" in app, "앱 글자 안전 처리(clean)"),
                  ("KIS_READ_ONLY" in wk and "kisAllowed(path, trId)" in wk, "한국투자증권 시세 전용 잠금"), ((ROOT / "worker/test/security.test.mjs").exists(), "서버 보안 시험")):
    if not ok_:
        sec.append(f"보안 장치가 코드에서 사라졌어요: {what}")
for i, m in enumerate(sec):
    alerts.append((f"sec:{m[:40]}", True, "보안 경보", m))

# 새 알림만 기록
state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {"seen": {}}
seen, new = state.get("seen", {}), []
for key, urgent, title, body in alerts:
    last = seen.get(key)
    if last and age_h(last) < 6:
        continue
    seen[key] = now.strftime("%Y-%m-%d %H:%M")
    new.append((key, urgent, title, body))
state = {"last_run_kst": now.strftime("%Y-%m-%d %H:%M"), "alerts_now": [a[2] for a in alerts],
         "seen": {k: v for k, v in seen.items() if age_h(v) < 72}}
STATE.parent.mkdir(parents=True, exist_ok=True)
if new:
    with BOARD.open("a", encoding="utf-8") as f:
        for i, (key, urgent, title, body) in enumerate(new, 1):
            f.write(f"\n### G-{now:%Y%m%d-%H%M}-{i} · {'알림(긴급)' if urgent else '알림'} · {title}\n- 시각: {now:%Y-%m-%d %H:%M} KST\n- 내용: {body}\n- 요청: {'Conrad 확인 바람 (긴급)' if urgent else 'Vernon 참고'}\n")
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(f"Argus {now:%H:%M}: 지금 알림 {len(alerts)}건 · 새로 적음 {len(new)}건")
for a in alerts:
    print(" -", ("[긴급] " if a[1] else "") + a[2])
sys.exit(2 if any(a[1] for a in new) else 0)
