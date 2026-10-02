"""Search never dead-ends: generic words, Remote, word order, fallback list."""
import asyncio, glob
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
async def rows(pg): return await pg.locator("a.jrow").count()
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        pg = await (await b.new_context()).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto(B + "/jobs/"); total = await rows(pg)
        await pg.goto(B + "/jobs/?q=Martech"); ok("S1 'Martech' shows the board, not a handful", await rows(pg) == total, (await rows(pg), total))
        await pg.goto(B + "/jobs/?q=martech&l=Remote"); n = await rows(pg)
        ok("S2 'martech' + Remote returns jobs", n > 0, n)
        await pg.goto(B + "/jobs/?q=zzqqxx"); body = await pg.locator("body").inner_text()
        ok("S3 nonsense search shows 'No exact match' + latest jobs", "No exact match" in body and "Latest MarTech jobs" in body and await rows(pg) > 0)
        await pg.goto(B + "/?q=zzqqxx#jl-listings"); body = await pg.locator("body").inner_text()
        ok("S4 homepage search fallback too", "Latest MarTech jobs" in body and await rows(pg) > 0)
        first = pg.locator("a.jrow").first; href = await first.get_attribute("href")
        await first.click(); await pg.wait_for_load_state()
        ok("S5 fallback job links open the job page", "/job/" in pg.url, pg.url)
        await pg.goto(B + "/jobs/?q=Marketing+Operations"); n1 = await rows(pg)
        await pg.goto(B + "/jobs/?q=operations+marketing"); n2 = await rows(pg)
        ok("S6 word order doesn't matter", n1 > 0 and n1 == n2, (n1, n2))
        m = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page()
        await m.goto(B + "/jobs/?q=zzqqxx"); w = await m.evaluate("document.documentElement.scrollWidth")
        ok("S7 mobile fallback page fits the screen", w <= 392 and await m.locator("a.jrow").count() > 0, w)
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
