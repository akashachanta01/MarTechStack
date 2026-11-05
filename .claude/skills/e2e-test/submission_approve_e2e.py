"""Nov 5 2026: held employer submission (Kalsec) approved by migration 0034.
Checks: hidden before (404, not in listings), live after on desktop + phone, JobPosting schema,
correct logo, unique title/description, apply link, appears on /jobs/ list, no JS errors."""
import asyncio, glob, json, subprocess
from playwright.async_api import async_playwright
B = "http://127.0.0.1:8765"; R = []
ROOT = "/home/user/MarTechStack"
def ok(n, c, i=""):
    R.append(bool(c)); print(("PASS " if c else "FAIL ") + n + (" — " + str(i) if i else ""))

def shell(code):
    return subprocess.run(["python", ROOT + "/manage.py", "shell", "-c", code],
                          capture_output=True, text=True, cwd=ROOT)

CREATE = ("from jobs.models import Job; "
          "j=Job.objects.create(title='Senior Digital Marketing Manager', company='Kalsec, Inc.', "
          "location='Kalamazoo, MI, United States', apply_url='https://recruiting2.ultipro.com/KAL1000KALSE/JobBoard/x', "
          "description='<p>The Senior Digital Marketing Manager owns the digital marketing ecosystem including the website, "
          "marketing automation, CRM alignment, analytics and related integrations.</p>' * 6, "
          "tags='User Submission: free', poster_email='kstrohm@kalsec.com', poster_name='Kendall Strohm', "
          "screening_status='pending', company_logo='https://www.google.com/s2/favicons?domain=perfumerflavorist.com&sz=128'); "
          "Job.objects.filter(pk=j.pk).update(slug='senior-digital-marketing-manager-at-kalsec-inc'); print('ID', j.pk)")
MIGRATE = ("import importlib; from django.apps import apps; "
           "importlib.import_module('jobs.migrations.0034_approve_kalsec_submission').forwards(apps, None); "
           "from jobs.models import Job; j=Job.objects.get(slug='senior-digital-marketing-manager-at-kalsec-inc'); "
           "print('STATE', j.screening_status, j.is_active)")

async def main():
    out = shell(CREATE)
    jid = int(out.stdout.split("ID")[-1].strip()) if "ID" in out.stdout else None
    ok("pending submission seeded", jid is not None, out.stderr[-200:])
    url = f"{B}/job/{jid}/senior-digital-marketing-manager-at-kalsec-inc/"
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        pg = await (await b.new_context()).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
        r = await pg.goto(url)
        ok("before approval: job page hidden (404/410)", r.status in (404, 410), r.status)
        await pg.goto(B + "/jobs/?q=Kalsec")
        ok("before approval: not in search results", await pg.locator("a[href*='kalsec']").count() == 0)

        out = shell(MIGRATE)
        ok("migration approves it", "STATE approved True" in out.stdout, (out.stdout[-80:], out.stderr[-200:]))
        out2 = shell(MIGRATE)
        ok("migration is safe to run twice", "STATE approved True" in out2.stdout, out2.stderr[-200:])

        for label, kw in (("desktop", {"viewport": {"width": 1280, "height": 900}}),
                          ("phone", {"viewport": {"width": 390, "height": 844}, "is_mobile": True})):
            pg = await (await b.new_context(**kw)).new_page(); pg.on("pageerror", lambda e: errs.append(str(e)))
            r = await pg.goto(url)
            t = await pg.title()
            d = await pg.locator('meta[name="description"]').get_attribute("content") or ""
            body = await pg.locator("body").inner_text()
            w = await pg.evaluate("document.documentElement.scrollWidth")
            ok(f"[{label}] job page live", r.status == 200 and "Kalsec" in body, r.status)
            ok(f"[{label}] unique title + description", "Senior Digital Marketing Manager" in t and "Kalsec" in t and 50 < len(d) <= 160, (t, d[:80]))
            ok(f"[{label}] fits screen", label == "desktop" or w <= 392, w)
            schemas = await pg.locator('script[type="application/ld+json"]').all_inner_texts()
            jp = [s for s in schemas if '"JobPosting"' in s]
            good = False
            if jp:
                data = json.loads(jp[0])
                good = data.get("hiringOrganization", {}).get("name", "").startswith("Kalsec") and data.get("validThrough") and data.get("datePosted")
            ok(f"[{label}] JobPosting schema with company, datePosted, validThrough", good, jp[:1][0][:120] if jp else "none")
            html = await pg.content()
            ok(f"[{label}] logo is Kalsec's, not the old wrong one", "perfumerflavorist" not in html, "")
            canon = await pg.locator('link[rel="canonical"]').get_attribute("href")
            ok(f"[{label}] canonical points at the job page", canon and canon.endswith(f"/job/{jid}/senior-digital-marketing-manager-at-kalsec-inc/"), canon)
            apply = pg.locator("a[href*='ultipro.com']")
            ok(f"[{label}] apply link goes to Kalsec's careers board", await apply.count() >= 1, await apply.count())
        pg = await (await b.new_context()).new_page()
        await pg.goto(B + "/jobs/?q=Kalsec")
        ok("after approval: appears in search results", await pg.locator("a[href*='kalsec']").count() >= 1)
        ok("no JS errors", not errs, errs[:3])
        await b.close()
    print(f"{sum(R)}/{len(R)} passed")

asyncio.run(main())
