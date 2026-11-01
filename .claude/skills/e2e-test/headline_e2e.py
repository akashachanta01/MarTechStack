"""Nov 2026 Google headline rewrite: job-title pages + salary guide, seeded production-size data."""
import asyncio, glob, re
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))
PAGES = ["/marketing-technology-analyst-jobs/", "/marketing-automation-specialist-jobs/",
         "/marketing-operations-manager-jobs/", "/salesforce-administrator-jobs/", "/crm-manager-jobs/"]
async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            for path in PAGES + ["/salary-guide/"]:
                r = await pg.goto(B + path)
                t = await pg.title()
                d = await pg.locator('meta[name="description"]').get_attribute("content")
                rows = await pg.locator("a.jrow").count()
                w = await pg.evaluate("document.documentElement.scrollWidth")
                good = r.status == 200 and 15 < len(t) <= 65 and 50 < len(d) <= 160 and "{{" not in t + d and " 0 " not in t
                if path != "/salary-guide/" and rows:
                    good = good and re.match(r"^\d+ ", t) and re.match(r"^\d+ live ", d)
                if path != "/salary-guide/" and rows:
                    good = good and t.split(" ")[0] == str(int(t.split(" ")[0]))
                ok(f"[{label}] {path}", good and (label == "desktop" or w <= 392), (r.status, t, d[:90], rows, w))
        # count in the headline matches the jobs listed on the page (first page shows up to 20)
        pg = await (await b.new_context()).new_page(); checked = 0
        for path in PAGES:
            await pg.goto(B + path); t = await pg.title(); rows = await pg.locator("a.jrow").count()
            if rows:
                n = int(t.split(" ")[0]); checked += 1
                ok(f"count in headline matches listed jobs {path}", rows == min(n, 20), (n, rows))
        ok("at least one title page with jobs checked", checked >= 1, checked)
        # Hiring Report page on desktop + phone
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            r = await pg.goto(B + "/martech-job-market-statistics/")
            t = await pg.title(); body = await pg.locator("body").inner_text()
            w = await pg.evaluate("document.documentElement.scrollWidth")
            n = int(t.split(":")[1].strip().split(" ")[0]) if ":" in t else -1
            ok(f"[{label}] hiring report loads, title has month + live count", r.status == 200 and "Hiring Report" in t and n > 100, (r.status, t))
            ok(f"[{label}] key findings + 5 tables + citation", "Key findings" in body and await pg.locator("table.ms-table").count() == 5 and "Source: MarTechJobs.io" in body, await pg.locator("table.ms-table").count())
            ok(f"[{label}] no last-month column before a snapshot exists", "vs last month" not in body)
            ok(f"[{label}] fits the screen", label == "desktop" or w <= 392, w)
            link = await pg.locator("table.ms-table a[href^='/companies/']").first.get_attribute("href")
            r2 = await pg.goto(B + link)
            ok(f"[{label}] top-company link opens the company page", r2.status == 200, (link, r2.status))
        # Surveys vs job postings blog post (migration 0031) on desktop + phone.
        # The E2E DB is built from models, so run the data migration's forwards() here.
        import subprocess
        out = subprocess.run(["python", "/home/user/MarTechStack/manage.py", "shell", "-c",
                              "import importlib; from django.apps import apps; "
                              "importlib.import_module('jobs.migrations.0031_blog_surveys_vs_job_postings').forwards(apps, None); "
                              "from jobs.models import BlogPost; print(BlogPost.objects.filter(slug='martech-surveys-vs-job-postings-2026').count())"],
                             capture_output=True, text=True, cwd="/home/user/MarTechStack")
        ok("post created from migration", out.stdout.strip().endswith("1"), (out.stdout[-80:], out.stderr[-200:]))
        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            r = await pg.goto(B + "/blog/martech-surveys-vs-job-postings-2026/")
            w = await pg.evaluate("document.documentElement.scrollWidth")
            body = await pg.locator("body").inner_text()
            ok(f"[{label}] surveys-vs-jobs post loads, fits, cites sources", r.status == 200 and (label == "desktop" or w <= 392)
               and "About the sources" in body and await pg.locator("article table, .post-content table, table").count() >= 1, (r.status, w))
        ok("no JS errors", not errs, errs[:3])
        print(f"\n{sum(R)}/{len(R)} passed"); await b.close()
asyncio.run(main())
