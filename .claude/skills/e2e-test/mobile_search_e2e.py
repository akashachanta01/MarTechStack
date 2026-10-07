"""Home search on phones: nothing cut off, full-width input + button, filters
usable, Remote panel inside the screen, search works; desktop unchanged."""
import asyncio, glob
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        for w in (390, 320):
            m = await (await b.new_context(viewport={"width": w, "height": 800}, is_mobile=True, has_touch=True)).new_page()
            m.on("pageerror", lambda e: errs.append(str(e)))
            await m.goto(B + "/")
            card = await m.locator(".searchcard").bounding_box()
            boxes = {}
            for sel in ['.s-field', '.s-go', '.s-select-wrap >> nth=0', '.s-select-wrap >> nth=1', '.s-remote-trigger']:
                boxes[sel] = await m.locator(sel).bounding_box()
            inside = all(bx and bx["x"] >= card["x"] - 1 and bx["x"] + bx["width"] <= card["x"] + card["width"] + 1 for bx in boxes.values())
            ok(f"M1 [{w}px] every search control fits inside the card", inside, {k: (round(v['x']), round(v['width'])) for k, v in boxes.items()})
            ok(f"M2 [{w}px] no sideways scrolling", await m.evaluate("document.documentElement.scrollWidth") <= w + 1)
            f, g = boxes['.s-field'], boxes['.s-go']
            ok(f"M3 [{w}px] search box and button full width, button below", g["y"] > f["y"] + f["height"] - 1 and abs(f["width"] - g["width"]) < 2)
            ok(f"M3b [{w}px] search box is full height (not squashed)", f["height"] >= 44, f["height"])
            fs = await m.evaluate("parseFloat(getComputedStyle(document.querySelector('.s-field input')).fontSize)")
            ok(f"M4 [{w}px] input text 16px (no iPhone zoom)", fs >= 16, fs)
            ph = await m.evaluate("(() => { const i = document.querySelector('.s-field input'); return i.scrollWidth <= i.clientWidth + 2; })()")
            if w == 390: ok(f"M5 [{w}px] remote button visible and full width", boxes['.s-remote-trigger']["width"] > card["width"] - 40)
            await m.locator(".s-remote-trigger").click(); await m.wait_for_timeout(300)
            pb = await m.locator(".s-remote-panel").bounding_box()
            ok(f"M6 [{w}px] Remote panel opens inside the screen", pb and pb["x"] >= 0 and pb["x"] + pb["width"] <= w + 1, pb)
            await m.locator(".s-remote-trigger").click()
            await m.fill(".s-field input", "marketo"); await m.locator(".s-go").click(); await m.wait_for_load_state()
            ok(f"M7 [{w}px] searching works", "q=marketo" in m.url, m.url)
        for path in ("/", "/jobs/"):
            m = await (await b.new_context(viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)).new_page()
            await m.goto(B + path); await m.locator(".s-remote-trigger").click(); await m.wait_for_timeout(1600)
            pb = await m.locator(".s-remote-panel").bounding_box()
            ok(f"M9 phone {path}: Remote panel scrolled fully into view", pb and pb["y"] >= 0 and pb["y"] + pb["height"] <= 844 + 8, pb)
        d = await (await b.new_context(viewport={"width": 1280, "height": 900})).new_page()
        await d.goto(B + "/")
        f = await d.locator(".s-field").bounding_box(); g = await d.locator(".s-go").bounding_box()
        ok("M8 desktop unchanged: search box and button on one row", abs(f["y"] - g["y"]) < 4)
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
