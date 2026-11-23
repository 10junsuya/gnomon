#!/usr/bin/env python3
"""노몬 QA 자동 검사기

앱(index.html)을 진짜 브라우저로 열어 모든 화면·시트·계산기를 눌러 보고
오류, 깨진 숫자(NaN 등), 화면 넘침, 너무 작은 버튼, 데이터 점검 결과를 모아
qa-out/report.json, report.md, 스크린샷으로 남긴다.

이 스크립트는 앱 파일을 절대 수정하지 않는다. 읽기와 화면 캡처만 한다.

사용:  python qa/run_qa.py --app index.html --out qa-out
환경변수 QA_CHROME 에 크롬 경로를 주면 그 크롬을 쓴다(없으면 Playwright 기본 크로미움).
"""
import argparse, json, os, re, sys, time, pathlib
from playwright.sync_api import sync_playwright

ROUTES = ["main", "home", "calendar", "news", "portfolio", "guide",
          "macro", "macro-price", "macro-job", "macro-rate", "macro-mkt", "macro-map-cpi", "check",
          "ahub", "amap", "amap-ai", "amap-semi", "amap-space", "amap-power", "amap-ai--sgus", "amap-semi--tsmc-az", "amap-space--artemis", "amap-power--crane"]  # Aleph 산업 지도 (옛 A 화면, 2026-11-20 대표 승인, Vernon V-20261119-1541-2)
VIEWPORTS = {"phone": (390, 844), "small": (320, 640), "desktop": (1280, 900)}
THEMES = ["light", "dark"]
TIMES = ["", "07:30", "09:02", "15:25", "23:50", "06:30"]
BAD_TEXT = re.compile(r"\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|\bnull\b")

PROBE = r"""
() => {
  const vw = window.innerWidth;
  const out = {overflow: [], small: [], noname: [], noalt: [], badText: [], docOverflow: 0};
  out.docOverflow = Math.max(0, document.documentElement.scrollWidth - vw);
  const visible = el => { const r = el.getBoundingClientRect(); const cs = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && cs.visibility !== "hidden" && cs.display !== "none" && !el.closest("[hidden]"); };
  const clipped = el => { for(let p = el.parentElement; p; p = p.parentElement){ const ox = getComputedStyle(p).overflowX; if(ox === "auto" || ox === "scroll" || ox === "hidden") return true; } return false; };
  const label = el => (el.getAttribute("aria-label") || el.innerText || el.textContent || el.value || el.getAttribute("title") || "").trim().replace(/\s+/g, " ").slice(0, 60);
  const scope = document.querySelector("#overlay.open #sheet") || document.body;
  scope.querySelectorAll("*").forEach(el => {
    if(!visible(el) || el.closest("svg")) return;
    const r = el.getBoundingClientRect();
    if(r.right > vw + 1 && !clipped(el) && el.children.length === 0) out.overflow.push({tag: el.tagName.toLowerCase(), text: label(el), right: Math.round(r.right), vw});
  });
  scope.querySelectorAll("button, a[href], [role=button], input, select, summary").forEach(el => {
    if(!visible(el)) return;
    const r = el.getBoundingClientRect();
    // 문장 속 용어 버튼·링크는 WCAG 2.2 예외(문장 안 대상)라 제외
    const inline = el.classList.contains("tword") || getComputedStyle(el).display === "inline";
    if(!inline && (r.width < 24 || r.height < 24)) out.small.push({tag: el.tagName.toLowerCase(), text: label(el), w: Math.round(r.width), h: Math.round(r.height)});
    if((el.tagName === "BUTTON" || el.getAttribute("role") === "button") && !label(el)) out.noname.push({html: el.outerHTML.slice(0, 120)});
  });
  scope.querySelectorAll("img").forEach(el => { if(!el.hasAttribute("alt")) out.noalt.push({src: (el.src || "").slice(0, 80)}); });
  const txt = scope.innerText || "";
  const m = txt.match(/.{0,30}(\bNaN\b|\bundefined\b|\bInfinity\b|\[object Object\]|\bnull\b).{0,30}/g);
  if(m) out.badText = m.slice(0, 10);
  return out;
}
"""

class QA:
    def __init__(self, app, out, chrome):
        self.app = pathlib.Path(app).resolve()
        self.out = pathlib.Path(out); (self.out / "shots").mkdir(parents=True, exist_ok=True)
        self.chrome = chrome
        self.findings = []
        self.pages_checked = 0
        self.seen = set()

    def add(self, sev, kind, where, detail):
        key = (sev, kind, re.sub(r"\[(phone|small|desktop)/(light|dark)/t=[^\]]*\]", "", where), json.dumps(detail, ensure_ascii=False, sort_keys=True))
        if key in self.seen: return
        self.seen.add(key)
        self.findings.append({"sev": sev, "kind": kind, "where": where, "detail": detail})

    def new_page(self, browser, vp, theme, sim=""):
        ctx = browser.new_context(viewport={"width": vp[0], "height": vp[1]}, device_scale_factor=1)
        ctx.add_init_script(f"try{{localStorage.setItem('themeMode', JSON.stringify('{theme}')); localStorage.setItem('tipSeen','true');}}catch(e){{}}")
        page = ctx.new_page()
        page._qa_errors = []
        page.on("pageerror", lambda e: page._qa_errors.append(str(e)))
        page.on("console", lambda m: page._qa_errors.append("console: " + m.text) if m.type == "error" and not re.search(r"Failed to load resource: net::ERR_(TUNNEL|NAME|INTERNET|PROXY|CONNECTION)", m.text) else None)  # 바깥 사진이 검사 환경 네트워크에서 막히는 건 앱 오류가 아님 (2026-11-22)
        page.goto(self.app.as_uri() + "#main")
        page.wait_for_timeout(300)
        page.evaluate("() => { const s = document.getElementById('splash'); if(s) s.remove(); }")
        if sim:
            page.evaluate(f"() => {{ const s = document.getElementById('simSel'); s.value = '{sim}'; s.dispatchEvent(new Event('change')); }}")
            page.wait_for_timeout(100)
        return ctx, page

    def probe(self, page, where):
        self.pages_checked += 1
        for e in page._qa_errors: self.add("error", "자바스크립트 오류", where, e)
        page._qa_errors.clear()
        r = page.evaluate(PROBE)
        for t in r["badText"]: self.add("error", "깨진 값 표시 (NaN 등)", where, t)
        if r["docOverflow"] > 1: self.add("warn", "화면 가로 넘침", where, f"페이지가 화면보다 {r['docOverflow']}px 넓어요")
        for o in r["overflow"][:5]: self.add("warn", "요소가 화면 밖으로 나감", where, o)
        for s in r["small"][:8]: self.add("warn", "누르기 작은 버튼 (24px 미만)", where, s)
        for n in r["noname"][:5]: self.add("warn", "이름 없는 버튼 (화면 낭독기)", where, n)
        for n in r["noalt"][:5]: self.add("warn", "대체 텍스트 없는 이미지", where, n)

    def shot(self, page, name, full=True):
        page.screenshot(path=str(self.out / "shots" / f"{name}.png"), full_page=full)

    def close_sheet(self, page):
        page.evaluate("() => { if(typeof closeSheet === 'function') closeSheet(); }")

    def run(self):
        with sync_playwright() as p:
            kw = {"args": ["--no-sandbox"]}
            if self.chrome: kw["executable_path"] = self.chrome
            browser = p.chromium.launch(**kw)
            meta = None
            # 1) 화면 × 크기 × 밤낮 × 시간대
            for vname, vp in VIEWPORTS.items():
                for theme in THEMES:
                    times = TIMES if (vname == "phone") else [""]
                    for sim in times:
                        ctx, page = self.new_page(browser, vp, theme, sim)
                        if meta is None:
                            meta = page.evaluate("() => ({etfs: ETFS.map(e=>e.code), inds: Object.keys(IND), stocks: Object.keys(STOCKS), tools: Object.keys(TOOLS), terms: Object.keys(GLOSS)})")
                        routes = ROUTES + [f"etf-{c}" for c in meta["etfs"]]
                        for r in routes:
                            page.evaluate(f"() => {{ location.hash = '{r}'; }}"); page.wait_for_timeout(120)
                            where = f"#{r} [{vname}/{theme}/t={sim or '실제'}]"
                            self.probe(page, where)
                            if sim == "" and vname in ("phone", "desktop"):
                                self.shot(page, f"{vname}-{theme}-{r}")
                        ctx.close()
            # 2) 시트·계산기·상세 (휴대폰, 밤낮)
            for theme in THEMES:
                ctx, page = self.new_page(browser, VIEWPORTS["phone"], theme)
                page.evaluate("() => { location.hash = 'macro'; }"); page.wait_for_timeout(100)
                for k in meta["inds"]:
                    page.evaluate(f"() => indSheet('{k}')"); page.wait_for_timeout(80)
                    page.evaluate("() => document.querySelectorAll('#sheet details').forEach(d => d.open = true)")
                    self.probe(page, f"지표 시트 {k} [{theme}]")
                    if theme == "light": self.shot(page, f"sheet-ind-{k}", full=True)
                    for cp in page.evaluate("() => [...document.querySelectorAll('#sheet [data-cp]')].map(b => b.dataset.cp)"):
                        page.evaluate(f"() => {{ const b = document.querySelector('#sheet [data-cp=\"{cp}\"]'); if(b) b.click(); }}"); page.wait_for_timeout(40)
                        self.probe(page, f"지표 시트 {k} 그래프 {cp} [{theme}]")
                    self.close_sheet(page)
                page.evaluate("() => { location.hash = 'home'; }"); page.wait_for_timeout(100)
                for t in meta["stocks"]:
                    page.evaluate(f"() => stockSheet('{t}')"); page.wait_for_timeout(50)
                    self.probe(page, f"종목 시트 {t} [{theme}]")
                    # 돈은 어디서 버나 · 업계에서의 위치: 둘 다 펼쳐서 확인
                    if page.evaluate("() => { const b=[...document.querySelectorAll('#sheet [data-acc]')]; b.forEach(x=>x.click()); return b.length; }"):
                        page.wait_for_timeout(30)
                        self.probe(page, f"매출 구성·업계 위치 {t} [{theme}]")
                        if theme == "light" and t in ("NVDA", "BRKB"): self.shot(page, f"sheet-money-{t}", full=True)
                    # 제품 카드: 분류마다 첫 카드를 펼쳐서 확인
                    for ci in range(page.evaluate("() => document.querySelectorAll('#sheet .pc').length")):
                        page.evaluate(f"() => document.querySelector('#sheet .pc[data-pcat=\"{ci}\"]').click()"); page.wait_for_timeout(30)
                        for pi in range(page.evaluate("() => document.querySelectorAll('#sheet .pgroup:not([hidden]) .phead').length")):
                            page.evaluate(f"() => document.querySelectorAll('#sheet .pgroup:not([hidden]) .phead')[{pi}].click()"); page.wait_for_timeout(30)
                            if page.evaluate("() => { const b=[...document.querySelectorAll('#sheet .pitem.open [data-pspec]')]; b.forEach(x=>x.click()); return b.length; }"):
                                page.wait_for_timeout(30)
                            self.probe(page, f"제품 카드 {t} 분류{ci} #{pi} [{theme}]")
                    self.close_sheet(page)
                for c in meta["etfs"]:
                    page.evaluate(f"() => openBrief('{c}')"); page.wait_for_timeout(60)
                    self.probe(page, f"브리핑 {c} [{theme}]"); self.close_sheet(page)
                page.evaluate("() => { location.hash = 'calendar'; }"); page.wait_for_timeout(100)
                for ev in page.evaluate("() => [...document.querySelectorAll('[data-evt]')].map(e => e.dataset.evt)"):
                    page.evaluate(f"() => eventSheet({json.dumps(ev)})"); page.wait_for_timeout(50)
                    self.probe(page, f"일정 시트 {ev} [{theme}]"); self.close_sheet(page)
                for w in ("kr", "us"):
                    page.evaluate(f"() => holiSheet('{w}')"); page.wait_for_timeout(60)
                    self.probe(page, f"휴장일 {w} [{theme}]"); self.close_sheet(page)
                page.evaluate("() => { location.hash = 'guide'; }"); page.wait_for_timeout(100)
                edge = ["0", "-5", "1000000000", "", "abc", "0.0001"]
                for tk in meta["tools"]:
                    page.evaluate(f"() => openTool('{tk}')"); page.wait_for_timeout(80)
                    self.probe(page, f"도구 {tk} 기본값 [{theme}]")
                    if theme == "light": self.shot(page, f"tool-{tk}")
                    names = page.evaluate("() => [...document.querySelectorAll('#sheet [data-calc] input')].map(i => i.name)")
                    for nm in names:
                        for v in edge:
                            page.evaluate(f"""() => {{ const i = document.querySelector('#sheet [data-calc] input[name="{nm}"]'); if(!i) return;
                                const old = i.value; i.value = {json.dumps(v)}; i.dispatchEvent(new Event('input', {{bubbles:true}})); i.dataset.old = old; }}""")
                            self.probe(page, f"도구 {tk} 입력 {nm}={v or '(빈칸)'} [{theme}]")
                            page.evaluate(f"""() => {{ const i = document.querySelector('#sheet [data-calc] input[name="{nm}"]'); if(!i) return; i.value = i.dataset.old; i.dispatchEvent(new Event('input', {{bubbles:true}})); }}""")
                    self.close_sheet(page)
                for term in meta["terms"][:40]:
                    page.evaluate(f"() => {{ const b = document.createElement('button'); b.dataset.term = {json.dumps(term)}; document.body.appendChild(b); b.click(); b.remove(); }}")
                    page.wait_for_timeout(20); self.probe(page, f"용어 {term} [{theme}]"); self.close_sheet(page)
                ctx.close()
            # 3) 시작 화면 전환
            for theme in THEMES:
                ctx = browser.new_context(viewport={"width": 390, "height": 844})
                ctx.add_init_script(f"try{{localStorage.setItem('themeMode', JSON.stringify('{theme}'));}}catch(e){{}}")
                page = ctx.new_page(); page._qa_errors = []
                page.on("pageerror", lambda e, pg=page: pg._qa_errors.append(str(e)))
                page.goto(self.app.as_uri() + "#main"); page.wait_for_timeout(2200)
                if theme == "light": self.shot(page, "splash", full=False)
                page.click("#splash"); page.wait_for_timeout(1800)
                if page.evaluate("() => !!document.getElementById('splash')"): self.add("error", "시작 화면", f"[{theme}]", "눌러도 시작 화면이 사라지지 않아요")
                page.click(".mlogo"); page.wait_for_timeout(1300)
                if not page.evaluate("() => !!document.getElementById('splash')"): self.add("error", "시작 화면", f"[{theme}]", "로고를 눌러도 시작 화면으로 돌아가지 않아요")
                page.click("#splash"); page.wait_for_timeout(1800)
                self.probe(page, f"시작 화면 왕복 [{theme}]")
                ctx.close()
            # 4) 데이터 점검기
            ctx, page = self.new_page(browser, VIEWPORTS["phone"], "light")
            chk = page.evaluate("() => runChecks()")
            for it in chk["items"]:
                self.add("error" if it["lv"] == "err" else "warn", "데이터 점검: " + it["area"], "runChecks", it["msg"])
            ctx.close()
            browser.close()
        return chk["count"]

    def write(self, data_checks):
        sev_order = {"error": 0, "warn": 1}
        self.findings.sort(key=lambda f: (sev_order.get(f["sev"], 9), f["kind"], f["where"]))
        e = sum(1 for f in self.findings if f["sev"] == "error"); w = sum(1 for f in self.findings if f["sev"] == "warn")
        summary = {"generated": time.strftime("%Y-%m-%d %H:%M:%S %Z"), "pages_checked": self.pages_checked,
                   "data_checks": data_checks, "errors": e, "warnings": w}
        (self.out / "report.json").write_text(json.dumps({"summary": summary, "findings": self.findings}, ensure_ascii=False, indent=1), encoding="utf-8")
        lines = [f"# 노몬 QA 자동 검사 보고서", "",
                 f"- 생성: {summary['generated']}", f"- 확인한 화면·상태: {self.pages_checked}개 · 데이터 점검 항목 {data_checks}개",
                 f"- 결과: **오류 {e}건 · 주의 {w}건**", "", "> 이 검사는 앱을 수정하지 않습니다. 찾은 내용만 기록합니다.", ""]
        by = {}
        for f in self.findings: by.setdefault((f["sev"], f["kind"]), []).append(f)
        for (sev, kind), lst in sorted(by.items(), key=lambda x: (sev_order.get(x[0][0], 9), x[0][1])):
            # 같은 내용이 여러 화면에서 나오면 한 줄로 묶는다
            grp = {}
            for f in lst:
                d = f["detail"] if isinstance(f["detail"], str) else json.dumps({k: v for k, v in f["detail"].items() if k not in ("right",)}, ensure_ascii=False)
                grp.setdefault(d, []).append(f["where"])
            lines.append(f"## {'오류' if sev == 'error' else '주의'} · {kind} ({len(grp)}종류, {len(lst)}곳)")
            for d, ws in sorted(grp.items(), key=lambda x: -len(x[1]))[:25]:
                more = f" 외 {len(ws) - 2}곳" if len(ws) > 2 else ""
                lines.append(f"- {d} — `{'`, `'.join(ws[:2])}`{more}")
            if len(grp) > 25: lines.append(f"- … 외 {len(grp) - 25}종류 (report.json 참고)")
            lines.append("")
        if not self.findings: lines.append("찾은 문제가 없어요.")
        (self.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
        return summary

def contact_sheets(out):
    """AI가 한눈에 볼 수 있게 캡처를 묶음별 한 장으로 만든다 (Pillow 있을 때만)."""
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        return []
    shots = sorted((out / "shots").glob("*.png"))
    groups = {}
    for f in shots:
        n = f.stem
        g = "-".join(n.split("-")[:2]) if n.startswith(("phone", "desktop")) else n.split("-")[0]
        groups.setdefault(g, []).append(f)
    made = []
    for g, files in groups.items():
        tw, th, cols = (300, 900, 5) if not g.startswith("desktop") else (480, 520, 3)
        rows = (len(files) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * (tw + 12) + 12, rows * (th + 40) + 12), "#888888")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(files):
            im = Image.open(f).convert("RGB")
            sc = tw / im.width; im = im.resize((tw, max(1, int(im.height * sc))))
            im = im.crop((0, 0, tw, min(th, im.height)))
            x = 12 + (i % cols) * (tw + 12); y = 12 + (i // cols) * (th + 40)
            sheet.paste(im, (x, y + 28)); d.text((x, y + 6), f.stem, fill="#000000")
        path = out / f"contact-{g}.png"; sheet.save(path); made.append(str(path))
    return made

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="index.html"); ap.add_argument("--out", default="qa-out")
    ap.add_argument("--strict", action="store_true", help="오류가 있으면 종료 코드 1")
    a = ap.parse_args()
    qa = QA(a.app, a.out, os.environ.get("QA_CHROME"))
    n = qa.run(); s = qa.write(n)
    s["contact_sheets"] = contact_sheets(qa.out)
    print(json.dumps(s, ensure_ascii=False))
    if a.strict and s["errors"]: sys.exit(1)

if __name__ == "__main__":
    main()
