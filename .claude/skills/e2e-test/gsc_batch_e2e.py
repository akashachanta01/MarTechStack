"""Search Console batch: analyst page, titles with live counts, Founder HQ Google table
(staff only). Needs the seeded server on :8765."""
import asyncio, glob
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        c = await b.new_context(); d = await c.new_page(); d.on("pageerror", lambda e: errs.append(str(e)))
        r = await d.goto(B + "/marketing-technology-analyst-jobs/")
        ok("G1 analyst page loads", r.status == 200)
        ok("G2 analyst H1", "Marketing Technology Analyst" in await d.inner_text("h1"))
        await d.goto(B + "/jobs/marketo/")
        t = await d.title(); ok("G3 tool title has live count + month", t[0].isdigit() and "Marketo Jobs — Updated" in t, t)
        await d.goto(B + "/remote/jobs/")
        t = await d.title(); ok("G4 remote title", "Remote MarTech Jobs — Updated" in t, t)
        await d.goto(B + "/jobs-by-tool/")
        t = await d.title(); ok("G5 directory title names platforms + total", "MarTech Jobs by Platform (" in t and "live roles)" in t and len(t) <= 65, t)
        r = await d.goto(B + "/staff/")
        ok("G6 Founder HQ still locked for visitors", "/staff/" not in d.url or r.status in (302, 403) or "login" in d.url.lower(), d.url)
        m = await (await b.new_context(viewport={"width": 390, "height": 844})).new_page()
        await m.goto(B + "/marketing-technology-analyst-jobs/")
        ok("G7 analyst page mobile: no sideways scroll", await m.evaluate("document.documentElement.scrollWidth") <= 390)
        await d.goto(B + "/")
        opts = await d.eval_on_selector_all("select[name=l] option", "els=>els.map(e=>e.textContent.trim())")
        import re as _re
        ok("G8 location dropdown: only All / Remote / 'Country (n)'",
           all(o in ("All Locations", "Remote") or _re.fullmatch(r"[A-Z][A-Za-z .&-]+ \(\d+\)", o) for o in opts), opts)
        await d.select_option("select[name=l]", index=len(opts) - 1)
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
