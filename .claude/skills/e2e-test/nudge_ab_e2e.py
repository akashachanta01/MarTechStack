"""Bottom-bar A/B test: scanner prompt for everyone (A/B winner Oct 30).
Needs the seeded server on :8765."""
import asyncio, glob, re
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
async def bar(b, variant, path, mobile=False):
    c = await b.new_context(viewport={"width": 390, "height": 844} if mobile else None)
    await c.add_init_script(f"try{{ if(!localStorage.getItem('mtj_nudge_ab')) localStorage.setItem('mtj_nudge_ab','{variant}') }}catch(e){{}}")
    pg = await c.new_page(); errs = []; pg.on("pageerror", lambda e: errs.append(str(e)))
    await pg.goto(B + path); await pg.wait_for_timeout(8600)
    vis = await pg.locator("#signup-bar").is_visible()
    return pg, vis, errs
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); allerr = []
        # Find a job page
        pg0 = await (await b.new_context()).new_page(); await pg0.goto(B + "/jobs/")
        href = await pg0.locator("a[href^='/job/']").first.get_attribute("href")
        pg, vis, e = await bar(b, "signup", href); allerr += e
        h = await pg.locator("#sb-cta").get_attribute("href")
        ok("N1 old 'signup' devices now get the scanner bar", vis and "/tools/resume-keyword-scanner/" in (h or ""), h)
        ok("N2 nobody is sent to sign-up from the bar", "/accounts/signup" not in (h or ""))
        pg, vis, e = await bar(b, "scanner", href); allerr += e
        h = await pg.locator("#sb-cta").get_attribute("href")
        ok("N3 scanner variant on job page links to scanner with this job", vis and re.search(r"/tools/resume-keyword-scanner/\?job=\d+", h or ""), h)
        ok("N4 scanner copy mentions this job", "this job" in await pg.locator("#sb-text").inner_text())
        await pg.locator("#sb-cta").click(); await pg.wait_for_load_state()
        ok("N5 click opens scanner with job preselected", "/tools/resume-keyword-scanner/" in pg.url, pg.url)
        pg, vis, e = await bar(b, "scanner", "/"); allerr += e
        ok("N6 scanner variant off job pages links to plain scanner", (await pg.locator("#sb-cta").get_attribute("href")).endswith("/tools/resume-keyword-scanner/"))
        pg, vis, e = await bar(b, "scanner", "/tools/resume-keyword-scanner/"); allerr += e
        ok("N7 no scanner bar on the scanner page itself", not vis)
        pg, vis, e = await bar(b, "scanner", href, mobile=True); allerr += e
        box = await pg.locator("#signup-bar").bounding_box()
        ok("N8 mobile: bar visible and fits screen", vis and box and box["width"] <= 390, box)
        await pg.locator("#signup-bar-close").click(); await pg.wait_for_timeout(500)
        await pg.reload(); await pg.wait_for_timeout(8600)
        ok("N9 dismiss snoozes the bar", not await pg.locator("#signup-bar").is_visible())
        c = await b.new_context(); pg = await c.new_page(); await pg.goto(B + "/"); await pg.wait_for_timeout(8600)
        h = await pg.locator("#sb-cta").get_attribute("href")
        ok("N10 fresh visitor gets the scanner bar", (h or "").endswith("/tools/resume-keyword-scanner/"), h)
        ok("Z no JS errors", not allerr, allerr[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
