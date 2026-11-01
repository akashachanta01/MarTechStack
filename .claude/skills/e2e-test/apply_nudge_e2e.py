"""After clicking Apply, anonymous visitors get a 'roles like this by email' box (Nov 2026).
Needs the seeded server on :8765."""
import asyncio, glob, subprocess
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
def django(code):
    out = subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c", code], capture_output=True, text=True, cwd="/home/user/MarTechStack")
    return (out.stdout.strip().splitlines() or [out.stderr[-300:]])[-1]
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        for tag, vp in (("desktop", None), ("phone", {"width": 390, "height": 844})):
            c = await b.new_context(viewport=vp); pg = await c.new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(B + "/jobs/")
            href = await pg.locator("a[href^='/job/']").first.get_attribute("href")
            await pg.goto(B + href)
            ok(f"A1 {tag} box hidden before Apply", not await pg.locator("#jd-nudge").is_visible())
            async with c.expect_page() as newp:
                await pg.locator(".js-apply").first.click()
            await (await newp.value).close()
            await pg.wait_for_timeout(500)
            ok(f"A2 {tag} box shows after Apply with email form", await pg.locator("#jd-nudge-form").is_visible())
            box = await pg.locator("#jd-nudge").bounding_box()
            ok(f"A3 {tag} box fits the screen", box and box["x"] >= 0 and box["x"] + box["width"] <= (vp or {"width": 1280})["width"] + 1, box)
            email = f"nudge-{tag}@example.com"
            await pg.fill("#jd-nudge-email", email); await pg.click("#jd-nudge-form button[type=submit]")
            await pg.wait_for_timeout(1500)
            msg = await pg.locator("#jd-nudge-msg").inner_text()
            n = django(f"from jobs.models import SavedSearch, PendingSubscriber, Subscriber; print(SavedSearch.objects.filter(email='{email}').count() + PendingSubscriber.objects.filter(email='{email}').count() + Subscriber.objects.filter(email='{email}').count())")
            ok(f"A4 {tag} email saved and confirmed on screen", n != "0" and "✓" in msg, (n, msg))
            await c.close()
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
