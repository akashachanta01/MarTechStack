"""Udemy-style courses: catalog + course pages on desktop and phone, rupees in
India / dollars elsewhere, member discount, logged-in details, request saved,
Courses tab + home link, dashboard courses card (no Pro)."""
import asyncio, glob, subprocess
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
SETUP = """
import importlib
from jobs.models import Job, Tool, Category, Course
seed = importlib.import_module('jobs.migrations.0023_courseinterest_user').SEED
for row in seed: Course.objects.update_or_create(slug=row['slug'], defaults=row)
cat,_=Category.objects.get_or_create(slug='cdp', defaults={'name':'CDP'})
t,_=Tool.objects.get_or_create(slug='adobe-experience-platform', defaults={'name':'Adobe Experience Platform','category':cat})
j=Job.objects.filter(is_active=True, screening_status='approved', company='Adobe').first(); j.tools.add(t)
from django.contrib.auth import get_user_model as g; U=g()
U.objects.filter(username='coursetest').exists() or U.objects.create_user('coursetest','ct@example.com','Pw-12345-x',first_name='Cara')
print(f'/job/{j.id}/{j.slug}/')
"""
def django(code):
    out = subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c", code],
                         capture_output=True, text=True, cwd="/home/user/MarTechStack")
    return (out.stdout.strip().splitlines() or [out.stderr[-300:]])[-1]
C = "/courses/adobe-aep-ajo-cja/"
async def login(pg):
    await pg.goto(B + "/accounts/login/?next=" + C)
    await pg.fill("input[name=login]", "ct@example.com"); await pg.fill("input[name=password]", "Pw-12345-x")
    await pg.click("form button[type=submit]"); await pg.wait_for_load_state()
async def main():
    adobe = django(SETUP)
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        def page(ctx):
            async def mk():
                pg = await ctx.new_page(); pg.on("pageerror", lambda e: errs.append(str(e))); return pg
            return mk()
        us = await page(await b.new_context(timezone_id="America/New_York", viewport={"width": 1280, "height": 900}))
        ind = await page(await b.new_context(timezone_id="Asia/Kolkata", viewport={"width": 1280, "height": 900}))
        mob = await page(await b.new_context(timezone_id="Asia/Kolkata", viewport={"width": 390, "height": 844}))
        # catalog
        await us.goto(B + "/courses/"); t = await us.locator("body").inner_text()
        ok("K1 catalog shows 3 course cards", await us.locator(".js-course-card").count() == 3)
        ok("K2 US visitor sees dollars", "US$625" in t and "₹" not in await us.locator(".cl-grid").inner_text())
        await ind.goto(B + "/courses/"); ti = await ind.locator(".cl-grid").inner_text()
        ok("K3 India visitor sees rupees (Indian grouping)", "₹60,000" in ti and "₹1,00,000" in ti and "US$" not in ti)
        ok("K4 no partner name or phone anywhere", "Infinite360" not in t and "9014649905" not in t)
        await us.locator(".js-course-card").first.click(); await us.wait_for_load_state()
        ok("K5 card opens course page", C in us.url, us.url)
        # detail desktop
        t = await us.locator("body").inner_text()
        ok("K6 course page has Udemy sections", all(x in t for x in ["What you'll learn", "Course content", "Who this course is for", "Request details"]))
        ok("K7 desktop price card visible, phone bar hidden", await us.locator(".cd-card").is_visible() and not await us.locator(".cd-mbar").is_visible())
        await us.locator(".cd-cur summary").nth(1).click()
        ok("K8 curriculum section expands", await us.locator(".cd-cur details").nth(1).get_attribute("open") is not None)
        await us.mouse.wheel(0, 1400); await us.wait_for_timeout(300)
        box = await us.locator(".cd-card").bounding_box()
        ok("K9 price card stays in view while scrolling (sticky)", box and 0 <= box["y"] < 900, box)
        # detail mobile
        await mob.goto(B + C)
        w = await mob.evaluate("document.documentElement.scrollWidth")
        ok("K10 phone: no sideways scrolling", w <= 392, w)
        ok("K11 phone: bottom price bar with button visible", await mob.locator(".cd-mbar").is_visible() and "₹60,000" in await mob.locator(".cd-mbar").inner_text())
        await mob.locator(".cd-mbar .cx-btn").click(); await mob.wait_for_timeout(500)
        top = (await mob.locator("#interest").bounding_box())["y"]
        ok("K12 phone: button jumps to the form", top < 844, top)
        ok("K13 phone: signup bar hidden on course pages", not await mob.locator("#signup-bar").is_visible())
        await mob.goto(B + "/courses/"); w = await mob.evaluate("document.documentElement.scrollWidth")
        ok("K14 phone catalog fits screen", w <= 392, w)
        # request (anonymous)
        await ind.goto(B + C + "?src=job_page")
        await ind.locator(".js-cx-form button[type=submit]").click(); await ind.wait_for_load_state()
        ok("K15 empty form shows errors", await ind.locator(".errorlist").count() > 0)
        await ind.fill("#id_name", "Asha Test"); await ind.fill("#id_email", "asha@example.com")
        await ind.check("input[name=program][value=cheaper]"); await ind.fill("#id_tool_note", "AJO only")
        await ind.locator(".js-cx-form button[type=submit]").click(); await ind.wait_for_load_state()
        ok("K16 thank-you shown", "Thanks" in await ind.locator(".cx-msg").inner_text())
        saved = django("from jobs.models import CourseInterest as C; c=C.objects.order_by('id').last(); print(c.email, c.course.slug, c.program, c.tool_note.replace(' ','_'), c.source_page)")
        ok("K17 saved with course, program, tool, source", saved == "asha@example.com adobe-aep-ajo-cja cheaper AJO_only job_page", saved)
        # member discount
        django("from jobs.models import Course; Course.objects.filter(slug='adobe-aep-ajo-cja').update(member_discount_pct=10); print('ok')")
        await ind.goto(B + C)
        ok("K18 logged out: 'Members save 10%' + sign-up link", "Members save 10%" in await ind.locator(".cd-card").inner_text())
        await login(us)
        ok("K19 log in returns to course page", C in us.url, us.url)
        card = await us.locator(".cd-card").inner_text()
        ok("K20 member price shown with 10% off", "US$562" in card and "Member price · 10% off" in card, card[:120])
        t = await us.locator("body").inner_text()
        ok("K21 signed in: 'Requesting as', no name/email boxes", "Requesting as" in t and await us.locator("#id_email").count() == 0)
        await us.locator(".js-cx-form button[type=submit]").click(); await us.wait_for_load_state()
        saved = django("from jobs.models import CourseInterest as C; c=C.objects.order_by('id').last(); print(c.email, c.user_id is not None, c.program)")
        ok("K22 signed-in request linked to account", saved == "ct@example.com True course", saved)
        await us.goto(B + "/accounts/dashboard/"); d = await us.locator("body").inner_text()
        ok("K23 dashboard: courses card with discount, no Go Pro", "MarTech courses" in d and "up to 10% off" in d and "Go Pro" not in d)
        # nav + home + job box
        await mob.goto(B + "/"); await mob.evaluate("toggleMobileMenu()"); await mob.wait_for_timeout(400)
        ok("K24 Courses tab in phone menu", await mob.locator('#mobile-menu a[href="/courses/"]').is_visible())
        await us.goto(B + "/"); ok("K25 Courses tab in desktop menu", await us.locator('nav a[href="/courses/"]').first.is_visible())
        await ind.goto(B + "/"); ok("K26 home page 'New courses' link", await ind.locator(".js-hero-course").is_visible())
        await ind.goto(B + adobe); ok("K27 course box on Adobe job page", await ind.locator(".mtj-course-box").is_visible())
        ok("Z no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
