"""Site-wide audit crawler (not a pass/fail suite): visits every sitemap URL plus
key app pages on desktop and phone and reports problems as JSON lines."""
import asyncio, glob, json, re, sys
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"
EXTRA = ["/", "/jobs/", "/courses/", "/tools/", "/tools/resume-keyword-scanner/", "/sponsor/", "/contact/", "/about/",
         "/for-employers/", "/post-job/", "/salary-guide/", "/blog/", "/accounts/login/", "/accounts/signup/",
         "/privacy/", "/terms/", "/directory/", "/companies/", "/jobs/?q=zzzz", "/nope-404/"]
async def main():
    import urllib.request
    xml = urllib.request.urlopen(B + "/sitemap.xml").read().decode()
    locs = re.findall(r"<loc>(.*?)</loc>", xml)
    urls = []
    for l in locs:
        if l.endswith(".xml"):
            sub = urllib.request.urlopen(B + urlparse(l).path).read().decode()
            urls += re.findall(r"<loc>(.*?)</loc>", sub)
        else:
            urls.append(l)
    paths = sorted({urlparse(u).path + (("?" + urlparse(u).query) if urlparse(u).query else "") for u in urls} | set(EXTRA))
    out = []
    def rep(page, kind, detail=""):
        out.append({"page": page, "kind": kind, "detail": str(detail)[:300]})
    titles = {}
    links = set()
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe)
        for label, ctxargs in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                               ("phone", {"viewport": {"width": 375, "height": 812}, "is_mobile": True, "has_touch": True})):
            ctx = await b.new_context(**ctxargs)
            pg = await ctx.new_page()
            cur = {"p": ""}
            pg.on("pageerror", lambda e: rep(cur["p"], f"js_error[{label}]", e))
            pg.on("console", lambda m: m.type == "error" and rep(cur["p"], f"console_error[{label}]", m.text))
            pg.on("requestfailed", lambda r: rep(cur["p"], f"request_failed[{label}]", r.url) if "127.0.0.1" in r.url else None)
            pg.on("response", lambda r: r.status >= 400 and "127.0.0.1" in r.url and urlparse(r.url).path != urlparse(cur["p"]).path and rep(cur["p"], f"asset_{r.status}[{label}]", r.url))
            for path in paths:
                cur["p"] = path
                try:
                    resp = await pg.goto(B + path, wait_until="load", timeout=30000)
                except Exception as e:
                    rep(path, f"load_fail[{label}]", e); continue
                st = resp.status if resp else 0
                if st >= 400 and path not in ("/nope-404/",):
                    rep(path, f"status_{st}[{label}]")
                if label == "phone":
                    sw = await pg.evaluate("document.documentElement.scrollWidth")
                    if sw > 377:
                        wide = await pg.evaluate("""() => { const r=[]; document.querySelectorAll('body *').forEach(e=>{const b=e.getBoundingClientRect(); if(b.right>380 && b.width>0 && getComputedStyle(e).position!=='fixed') r.push((e.tagName+'.'+(e.className||'')).slice(0,60)+':'+Math.round(b.right))}); return r.slice(0,4); }""")
                        rep(path, "phone_overflow", f"{sw}px {wide}")
                    small = await pg.evaluate("""() => [...document.querySelectorAll('a,button')].filter(e=>{const b=e.getBoundingClientRect(); return b.width>0 && b.height>0 && b.height<24 && b.width<24 && getComputedStyle(e).visibility!=='hidden'}).length""")
                    if small > 3: rep(path, "phone_tiny_tap_targets", small)
                    continue
                info = await pg.evaluate("""() => ({
                  title: document.title, desc: (document.querySelector('meta[name=description]')||{}).content||'',
                  canon: (document.querySelector('link[rel=canonical]')||{}).href||'',
                  robots: (document.querySelector('meta[name=robots]')||{}).content||'',
                  h1: [...document.querySelectorAll('h1')].map(h=>h.innerText.trim()),
                  noalt: [...document.querySelectorAll('img')].filter(i=>!i.hasAttribute('alt')).map(i=>i.src).slice(0,3),
                  links: [...document.querySelectorAll('a[href]')].map(a=>a.getAttribute('href')),
                  emptylinks: [...document.querySelectorAll('a[href]')].filter(a=>!a.innerText.trim() && !a.getAttribute('aria-label') && !a.querySelector('img[alt]')).length,
                  ld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s=>{try{JSON.parse(s.textContent);return 'ok'}catch(e){return 'bad'}}),
                  lorem: /lorem ipsum|TODO|FIXME|\\{\\{|\\{%|undefined|NaN|None\\b/.test(document.body.innerText) ? (document.body.innerText.match(/.{0,40}(lorem ipsum|TODO|FIXME|\\{\\{|\\{%|undefined|NaN|None\\b).{0,40}/)||[''])[0] : ''
                })""")
                noindex = "noindex" in info["robots"]
                t = info["title"]
                if not t: rep(path, "no_title")
                elif len(t) > 70: rep(path, "title_too_long", f"{len(t)}: {t}")
                if not noindex:
                    titles.setdefault(t, []).append(path)
                    if not info["desc"]: rep(path, "no_meta_description")
                    elif len(info["desc"]) > 165: rep(path, "meta_desc_too_long", len(info["desc"]))
                    elif len(info["desc"]) < 50: rep(path, "meta_desc_too_short", info["desc"])
                    if not info["canon"]: rep(path, "no_canonical")
                if len(info["h1"]) != 1 and st < 400: rep(path, "h1_count", info["h1"])
                if info["noalt"]: rep(path, "img_no_alt", info["noalt"])
                if info["emptylinks"]: rep(path, "links_without_text", info["emptylinks"])
                if "bad" in info["ld"]: rep(path, "bad_json_ld")
                if info["lorem"]: rep(path, "suspicious_text", info["lorem"])
                for h in info["links"]:
                    if h and not h.startswith(("#", "mailto:", "tel:", "javascript:")):
                        u = urljoin(B + path, h)
                        if urlparse(u).netloc == "127.0.0.1:8765":
                            links.add((urlparse(u).path + (("?" + urlparse(u).query) if urlparse(u).query else ""), path))
            await ctx.close()
        for t, ps in titles.items():
            if len(ps) > 1: rep(ps[0], "duplicate_title", f"{t} :: {ps[:4]}")
        # check every internal link once
        seen = {}
        for href, src in sorted(links):
            key = href.split("#")[0]
            if key in seen or key.startswith(("/admin", "/accounts/logout", "/staff")): continue
            try:
                r = await b.new_context()
                rr = await r.request.get(B + key, max_redirects=5, timeout=20000)
                seen[key] = rr.status
                if rr.status >= 400: rep(src, f"broken_link_{rr.status}", key)
                await r.close()
            except Exception as e:
                rep(src, "broken_link_err", f"{key} {e}")
        await b.close()
    print(json.dumps({"pages": len(paths), "links_checked": len(seen), "issues": out}))
asyncio.run(main())
