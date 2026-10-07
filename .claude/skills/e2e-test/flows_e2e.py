"""Key visitor flows end to end, desktop + phone: contact, sponsor, footer
newsletter, post a job, sign up -> dashboard, password reset, job page apply,
404 page, company + salary + blog pages."""
import asyncio, glob, subprocess
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
def django(code):
    out = subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c", code], capture_output=True, text=True, cwd="/home/user/MarTechStack")
    return (out.stdout.strip().splitlines() or [out.stderr[-300:]])[-1]
async def body(pg): return await pg.locator("body").inner_text()
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            tag = f"[{label}]"
            # contact
            await pg.goto(B + "/contact/")
            await pg.fill("#id_message", f"Audit test message {label}"); await pg.fill("form #id_email", "audit@example.com")
            await pg.locator("#id_message").evaluate("e => e.form.requestSubmit()"); await pg.wait_for_load_state()
            ok(f"F1 {tag} contact form sends", "Thanks" in await body(pg) or "thank" in (await body(pg)).lower())
            # sponsor
            await pg.goto(B + "/sponsor/")
            await pg.fill("#id_company", f"Acme {label}"); await pg.fill("#id_name", "Sam"); await pg.fill("form.js-sp-form #id_email", "sam@acme.test")
            await pg.locator("form.js-sp-form button[type=submit]").click(); await pg.wait_for_load_state()
            saved = django(f"from jobs.models import SponsorInquiry as S; print(S.objects.filter(company='Acme {label}').count())")
            ok(f"F2 {tag} sponsor enquiry saved + thank-you", saved == "1" and "Thanks" in await body(pg), saved)
            # footer newsletter
            await pg.goto(B + "/")
            await pg.locator("#footer-subscribe-form input[type=email]").fill(f"news-{label}@example.com")
            await pg.locator("#footer-subscribe-form button").click(); await pg.wait_for_timeout(1500)
            msg = await pg.locator("#footer-sub-message").inner_text()
            ok(f"F3 {tag} footer newsletter sign-up confirms", len(msg.strip()) > 5 and "error" not in msg.lower(), msg[:80])
            # post a job
            await pg.goto(B + "/post-job/")
            await pg.fill("#id_title", f"Marketing Ops Manager {label}"); await pg.fill("#id_company", "Audit Co")
            await pg.fill("#id_location", "Remote"); await pg.check("#id_work_arrangement_0")
            await pg.locator("#id_description").evaluate("(e) => { e.value = 'We need a Marketo and Salesforce expert to run campaigns, lead scoring and reporting. '.repeat(4); e.dispatchEvent(new Event('input')); }")
            await pg.fill("#id_apply_url", "https://example.com/apply")
            await pg.locator("#id_title").evaluate("e => e.form.requestSubmit()"); await pg.wait_for_load_state()
            n = django(f"from jobs.models import Job; print(Job.objects.filter(title='Marketing Ops Manager {label}').count())")
            errtxt = await pg.locator(".errorlist").all_inner_texts()
            ok(f"F4 {tag} post-a-job submission saved", n == "1", (n, pg.url, errtxt[:3]))
            # signup -> dashboard
            await pg.goto(B + "/accounts/signup/")
            em = f"newuser-{label}@example.com"
            await pg.fill("input[name=email]", em)
            for sel in ("input[name=password1]", "input[name=password]"):
                if await pg.locator(sel).count(): await pg.fill(sel, "Very-Strong-Pw-9182")
            if await pg.locator("input[name=password2]").count(): await pg.fill("input[name=password2]", "Very-Strong-Pw-9182")
            if await pg.locator("input[name=username]").count(): await pg.fill("input[name=username]", f"nu{label}")
            await pg.locator("form button[type=submit]").first.click(); await pg.wait_for_load_state()
            made = django(f"from django.contrib.auth import get_user_model as g; print(g().objects.filter(email='{em}').count())")
            ok(f"F5 {tag} sign-up creates account", made == "1", (made, pg.url))
            await pg.goto(B + "/accounts/dashboard/")
            ok(f"F6 {tag} new member reaches dashboard with courses card", "MarTech courses" in await body(pg), pg.url)
            await pg.goto(B + "/accounts/logout/")
            if await pg.locator("form button[type=submit]").count(): await pg.locator("form button[type=submit]").first.click(); await pg.wait_for_load_state()
            # password reset
            await pg.goto(B + "/accounts/password/reset/")
            await pg.fill("input[name=email]", em); await pg.locator("form button[type=submit]").first.click(); await pg.wait_for_load_state()
            ok(f"F7 {tag} password reset accepted", "/password/reset/done" in pg.url or "sent" in (await body(pg)).lower(), pg.url)
            # job page apply
            await pg.goto(B + "/jobs/"); href = await pg.locator("a.jrow").first.get_attribute("href")
            await pg.goto(B + href)
            ap = pg.locator("a:has-text('Apply')").first
            ok(f"F8 {tag} job page has an Apply link to the company", await ap.count() and (await ap.get_attribute("href") or "").startswith("http"), await ap.get_attribute("href") if await ap.count() else None)
            ld = await pg.evaluate("[...document.querySelectorAll('script[type=\"application/ld+json\"]')].some(s => s.textContent.includes('JobPosting'))")
            ok(f"F9 {tag} job page has JobPosting schema", ld)
            # 404
            r = await pg.goto(B + "/definitely-not-a-page/")
            ok(f"F10 {tag} dead link returns 404 status", r.status == 404, r.status)
            # misc pages render
            for path in ("/companies/", "/salary-guide/", "/blog/", "/about/", "/privacy/", "/terms/", "/for-employers/", "/martech-job-market-statistics/"):
                r = await pg.goto(B + path)
                w = await pg.evaluate("document.documentElement.scrollWidth")
                ok(f"F11 {tag} {path} loads and fits", r.status == 200 and (label == "desktop" or w <= 392), (r.status, w))
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
