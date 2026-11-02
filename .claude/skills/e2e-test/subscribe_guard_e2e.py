"""Subscribe bot guard (Nov 2026): a real browser sign-up is saved; a direct POST is not."""
import asyncio, glob, subprocess, urllib.request, urllib.parse, http.cookiejar, re
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
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            await pg.goto(B + "/delhi/jobs/")
            em = f"real-{label}@example.com"
            await pg.locator("#footer-subscribe-form input[type=email]").fill(em)
            await pg.locator("#footer-subscribe-form button").click(); await pg.wait_for_timeout(1500)
            n = django(f"from jobs.models import PendingSubscriber as P; print(P.objects.filter(email='{em}').count())")
            ok(f"[{label}] real footer sign-up saved (confirmation pending)", n == "1", n)
        # bot-style direct POST: fetch the page for a CSRF cookie, then POST without the JS token
        cj = http.cookiejar.CookieJar(); op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
        html = op.open(B + "/delhi/jobs/").read().decode()
        csrf = next((c.value for c in cj if c.name == "csrftoken"), "")
        data = urllib.parse.urlencode({"email": "victim@example.com", "csrfmiddlewaretoken": csrf}).encode()
        req = urllib.request.Request(B + "/subscribe/", data=data, headers={"Referer": B + "/delhi/jobs/", "X-CSRFToken": csrf})
        body = op.open(req).read().decode()
        n = django("from jobs.models import PendingSubscriber as P; print(P.objects.filter(email='victim@example.com').count())")
        ok("direct POST without page token: normal reply, nothing saved", '"success": true' in body and n == "0", (body[:80], n))
        ok("no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
