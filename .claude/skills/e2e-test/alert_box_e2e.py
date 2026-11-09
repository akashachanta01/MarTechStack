"""Nov 9 2026: platform job-alert box in the job page sidebar with a real new-roles count.
Desktop: visible without scrolling. Phone: fits. A real sign-up through it saves a SavedSearch."""
import asyncio, glob, subprocess
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
def django(code):
    out = subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c", code], capture_output=True, text=True, cwd="/home/user/MarTechStack")
    return (out.stdout.strip().splitlines() or [out.stderr[-300:]])[-1]
async def main():
    url = django("from jobs.models import Job; j=Job.objects.filter(is_active=True, screening_status='approved', tools__slug='marketo').first(); print(f'/job/{j.id}/{j.slug}/')")
    ok("seeded job with Marketo found", url.startswith("/job/"), url)
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            r = await pg.goto(B + url)
            box = pg.locator(".jd-sidebar #jd-alert-form")
            ok(f"[{label}] job page loads, alert box is in the sidebar", r.status == 200 and await box.count() == 1, r.status)
            txt = await pg.locator(".jd-side-alert").inner_text()
            ok(f"[{label}] box says 'only when new Marketo roles go live'", "only when new Marketo roles go live" in txt, txt[:120])
            if label == "desktop":
                bb = await box.bounding_box()
                ok("[desktop] box visible without scrolling (top < 900px)", bb and bb["y"] < 900, bb)
            w = await pg.evaluate("document.documentElement.scrollWidth")
            ok(f"[{label}] page fits the screen", label == "desktop" or w <= 392, w)
            em = f"alertbox-{label}@example.com"
            await box.scroll_into_view_if_needed()
            await pg.locator("#jd-alert-form input[type=email]").fill(em)
            await pg.locator("#jd-alert-form button").click(); await pg.wait_for_timeout(1500)
            msg = await pg.locator("#jd-alert-form-msg").inner_text()
            n = django(f"from jobs.models import SavedSearch as S; print(S.objects.filter(email='{em}').count())")
            ok(f"[{label}] real sign-up saves a Marketo alert and shows a message", n == "1" and len(msg.strip()) > 0, (n, msg[:80]))
        pg = await (await b.new_context()).new_page()
        r = await pg.goto(B + "/jobs/marketo/")
        ok("Marketo platform page still shows the alert box", r.status == 200 and await pg.locator("#td-alert-form").count() == 1, r.status)
        ok("no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
