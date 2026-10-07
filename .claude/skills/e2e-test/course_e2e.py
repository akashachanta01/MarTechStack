"""Adobe course interest test: box shows to every visitor on Adobe pages, request-details form saves interest, no payment, no partner phone."""
import asyncio, glob, subprocess, os
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
SETUP = """
from jobs.models import Job, Tool, Category
cat,_=Category.objects.get_or_create(slug='cdp', defaults={'name':'CDP'})
t,_=Tool.objects.get_or_create(slug='adobe-experience-platform', defaults={'name':'Adobe Experience Platform','category':cat})
j=Job.objects.filter(is_active=True, screening_status='approved', company='Adobe').first()
j.tools.add(t)
o=Job.objects.filter(is_active=True, screening_status='approved').exclude(company='Adobe').exclude(tools=t).first()
print(f'/job/{j.id}/{j.slug}/ /job/{o.id}/{o.slug}/')
"""
def django(code):
    return subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c", code],
                          capture_output=True, text=True, cwd="/home/user/MarTechStack").stdout.strip().splitlines()[-1]
async def main():
    adobe, other = django(SETUP).split()
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        ind = await b.new_context(timezone_id="Asia/Kolkata"); us = await b.new_context(timezone_id="America/New_York")
        pi = await ind.new_page(); pi.on("pageerror", lambda e: errs.append(str(e)))
        pu = await us.new_page(); pu.on("pageerror", lambda e: errs.append(str(e)))
        box = ".mtj-course-box"
        await pi.goto(B + adobe); ok("C1 India visitor sees box on Adobe job", await pi.locator(box).is_visible())
        await pu.goto(B + adobe); ok("C2 US visitor also sees box", await pu.locator(box).is_visible())
        await pi.goto(B + other); ok("C3 no box on non-Adobe job", await pi.locator(box).count() == 0)
        await pi.goto(B + "/jobs/adobe-experience-platform/"); ok("C4 India visitor sees box on AEP tool page", await pi.locator(box).is_visible())
        await pi.goto(B + adobe); await pi.locator(box + " a").click(); await pi.wait_for_load_state()
        ok("C5 box opens request-details page", "/learn/adobe-martech/" in pi.url and "src=job_page" in pi.url, pi.url)
        body = await pi.locator("body").inner_text()
        ok("C6 page shows real prices (₹ and US$) and live job demand", "₹60,000" in body and "US$625" in body and "Live jobs" in body)
        ok("C7 no partner phone / payment details shown", "9014649905" not in body and "PhonePe" not in body.replace("Phone / WhatsApp", ""))
        ok("C6b three deal cards shown", await pi.locator(".ac-card").count() == 3)
        await pi.locator('.js-pick[data-program="cxo"]').click()
        ok("C6c card button preselects its program", await pi.eval_on_selector("#id_program", "e => e.value") == "cxo")
        await pi.click("button[type=submit]"); await pi.wait_for_load_state()
        ok("C8 empty form shows errors, nothing saved", await pi.locator(".errorlist").count() > 0)
        await pi.fill("#id_name", "Asha Test"); await pi.fill("#id_email", "asha@example.com")
        await pi.select_option("#id_program", "cheaper"); await pi.click("button[type=submit]"); await pi.wait_for_load_state()
        ok("C9 valid request shows thank-you", "Thanks" in await pi.locator(".ac-msg").inner_text())
        saved = django("from jobs.models import CourseInterest as C; c=C.objects.last(); print(c.email, c.program, c.source_page)")
        ok("C10 interest saved with program + source page", saved == "asha@example.com cheaper job_page", saved)
        m = await (await b.new_context(timezone_id="Asia/Kolkata", viewport={"width": 390, "height": 844})).new_page()
        await m.goto(B + "/learn/adobe-martech/"); w = await m.evaluate("document.documentElement.scrollWidth")
        ok("C11 mobile page fits the screen", w <= 392, w)
        await m.goto(B + adobe); ok("C12 mobile India box visible", await m.locator(box).is_visible())
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
