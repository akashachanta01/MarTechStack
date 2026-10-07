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
        ok("C5 box opens request-details page", "/courses/" in pi.url and "src=job_page" in pi.url, pi.url)
        body = await pi.locator("body").inner_text()
        ok("C6 India visitor sees rupee prices only + live job demand", "₹60,000" in body and "US$625" not in body and "Live jobs" in body)
        ok("C6a per-tool pricing note shown", "Only need one tool?" in body)
        await pu.goto(B + "/courses/"); ub = await pu.locator(".ac-cards").inner_text()
        uo = await pu.locator("#id_program").inner_text()
        ok("C6d US visitor sees dollar prices only", "US$625" in ub and "₹" not in ub and "US$625" in uo and "₹" not in uo, ub[:80])
        ok("C7 no partner name, phone or payment details", "9014649905" not in body and "Infinite360" not in body and "PhonePe" not in body.replace("Phone / WhatsApp", ""))
        ok("C6b three deal cards shown", await pi.locator(".ac-card").count() == 3)
        await pi.locator('.js-pick[data-program="cxo"]').click()
        ok("C6c card button preselects its program", await pi.eval_on_selector("#id_program", "e => e.value") == "cxo")
        await pi.click("button[type=submit]"); await pi.wait_for_load_state()
        ok("C8 empty form shows errors, nothing saved", await pi.locator(".errorlist").count() > 0)
        await pi.fill("#id_name", "Asha Test"); await pi.fill("#id_email", "asha@example.com")
        await pi.select_option("#id_program", "cheaper"); await pi.fill("#id_tool_note", "AJO only"); await pi.click("button[type=submit]"); await pi.wait_for_load_state()
        ok("C9 valid request shows thank-you", "Thanks" in await pi.locator(".ac-msg").inner_text())
        saved = django("from jobs.models import CourseInterest as C; c=C.objects.order_by('id').last(); print(c.email, c.program, c.source_page, c.tool_note)")
        ok("C10 interest saved with program, tool and source page", saved == "asha@example.com cheaper job_page AJO only", saved)
        m = await (await b.new_context(timezone_id="Asia/Kolkata", viewport={"width": 390, "height": 844})).new_page()
        await m.goto(B + "/courses/"); w = await m.evaluate("document.documentElement.scrollWidth")
        ok("C11 mobile page fits the screen", w <= 392, w)
        await m.goto(B + adobe); ok("C12 mobile India box visible", await m.locator(box).is_visible())
        await pu.goto(B + "/"); ok("C13 home page shows New courses link", await pu.locator(".js-hero-course").is_visible())
        await pu.locator(".js-hero-course").click(); await pu.wait_for_load_state()
        ok("C14 home link opens Courses page", "/courses/" in pu.url, pu.url)
        ok("C15 Courses tab in desktop nav", await pu.locator('nav a[href="/courses/"]').first.is_visible())
        await m.goto(B + "/"); await m.evaluate("toggleMobileMenu()"); await m.wait_for_timeout(400)
        ok("C16 Courses tab in mobile menu", await m.locator('#mobile-menu a[href="/courses/"]').is_visible())
        await pu.goto(B + "/courses/")
        ok("C17 logged-out visitor sees Log in prompt", "Already have a MarTechJobs account?" in await pu.locator("body").inner_text())
        django("from django.contrib.auth import get_user_model as g; U=g(); u=U.objects.filter(username='coursetest').first() or U.objects.create_user('coursetest','ct@example.com','Pw-12345-x',first_name='Cara'); print('ok')")
        await pu.goto(B + "/accounts/login/?next=/courses/%23interest")
        await pu.fill("input[name=login]", "ct@example.com"); await pu.fill("input[name=password]", "Pw-12345-x")
        await pu.click("form button[type=submit]"); await pu.wait_for_load_state()
        ok("C18 log in returns to Courses page", "/courses/" in pu.url, pu.url)
        t = await pu.locator("body").inner_text()
        ok("C19 signed-in visitor sees 'Requesting as' and no name/email boxes", "Requesting as" in t and await pu.locator("#id_email").count() == 0)
        await pu.select_option("#id_program", "other"); await pu.fill("#id_tool_note", "Braze"); await pu.click(".js-ac-form button[type=submit]"); await pu.wait_for_load_state()
        saved = django("from jobs.models import CourseInterest as C; c=C.objects.order_by('id').last(); print(c.email, c.program, c.user_id is not None)")
        ok("C20 signed-in request linked to account", saved == "ct@example.com other True", saved)
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
