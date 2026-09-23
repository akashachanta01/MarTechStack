"""Resume Match phases 2-4 E2E: fit badges, My Matches, AI tailor + docx + Pro gate,
weekly email render. Needs the seeded server on :8765 started with MTJ_FAKE_AI=1.
Run from a scratch dir: python /path/to/phases_e2e.py"""
import asyncio, glob, io, re
from playwright.async_api import async_playwright

B = "http://127.0.0.1:8765"; R = []
def ok(name, cond, info=""):
    R.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name + (" — " + str(info) if info else ""))

RES_TXT = ("Jane Doe\nSenior Marketing Ops Specialist\n"
           "- Administered Marketo; built lead score model lifting MQL-to-SQL conversion 22%\n"
           "- Ran Pardot nurture campaigns for 40k contacts across three regions\n"
           "- Managed SFMC email sends and journeys for the global team\n"
           "- Partnered with sales on routing rules and pipeline reporting\n"
           "- Owned Salesforce attribution dashboards for 5 regions")

async def main():
    async with async_playwright() as p:
        exe = (glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome', recursive=True))[0]
        b = await p.chromium.launch(executable_path=exe); errs = []
        async def newpage(w=1280, h=900):
            c = await b.new_context(viewport={"width": w, "height": h}, accept_downloads=True); pg = await c.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            return pg
        async def login(pg, email):
            await pg.goto(B + "/accounts/login/"); await pg.fill("input[name=login]", email)
            await pg.fill("input[name=password]", "pw12345!x"); await pg.click("form button[type=submit]"); await pg.wait_for_timeout(900)

        # ---------- Phase 2 ----------
        anon = await newpage(); await anon.goto(B + "/jobs/"); await anon.wait_for_timeout(1200)
        ok("P2.1 anonymous: no fit badges, no scores request", await anon.locator(".mtj-fit-pill").count() == 0)
        u = await newpage(); await login(u, "jane@example.com")
        await u.goto(B + "/jobs/"); await u.wait_for_timeout(1200)
        ok("P2.2 signed-in without resume: no badges", await u.locator(".mtj-fit-pill").count() == 0)
        await u.goto(B + "/tools/resume-keyword-scanner/?job=1"); await u.click("#rm-paste-toggle"); await u.fill("#rm-resume", RES_TXT)
        await u.click("#rm-btn"); await u.wait_for_selector("#rm-results", state="visible")
        await u.goto(B + "/jobs/"); await u.wait_for_selector(".mtj-fit-pill", timeout=15000)
        n = await u.locator(".mtj-fit-pill").count(); ok("P2.3 saved resume -> badges on job cards", n > 5, f"{n} badges")
        await u.evaluate("document.addEventListener('click',function(e){if(e.target.closest('a'))e.preventDefault()},true)")
        await u.locator("a[data-mtj-fit]").first.click()
        ok("T1 fit badge job click tracked", "fit_badge_job_click" in await u.evaluate("JSON.stringify(dataLayer.map(e=>e.event))"))
        txt = await u.locator(".mtj-fit-pill").first.inner_text(); ok("P2.4 badge reads like '4/9 match'", re.match(r"\d+/\d+ match", txt), txt)
        await u.goto(B + "/job/1/marketing-operations-manager-at-acme/")
        ok("P2.5a banner hidden (not an empty box) before scores load", await u.evaluate("getComputedStyle(document.getElementById('mtj-fit')).display") == "none" or "Your fit" in await u.inner_text("#mtj-fit"))
        await u.wait_for_selector("#mtj-fit", state="visible", timeout=15000)
        ok("P2.5 job page fit banner", "Your fit:" in await u.inner_text("#mtj-fit"))
        await u.goto(B + "/accounts/matches/")
        rows = await u.locator(".mm-row").count(); first = await u.locator(".mm-row .t").first.inner_text()
        ok("P2.6 My Matches ranks best fit first", rows > 0 and "Marketo & SFMC" in first, first)
        await u.evaluate("document.addEventListener('click',function(e){if(e.target.closest('a.t'))e.preventDefault()},true)")
        await u.locator(".mm-row a.t").first.click()
        ok("T2 My Matches job click tracked", "my_matches_job_click" in await u.evaluate("JSON.stringify(dataLayer.map(e=>e.event))"))
        await u.click("text=All jobs by fit"); ok("P2.7 'All jobs by fit' tab", await u.locator(".mm-row").count() >= rows)
        m = await newpage(390, 844); await login(m, "jane@example.com"); await m.goto(B + "/accounts/matches/")
        ok("P2.8 My Matches mobile no horizontal scroll", await m.evaluate("document.documentElement.scrollWidth") <= 390)
        await u.goto(B + "/")
        ok("P2.9 'My Matches' in account menu", await u.locator("a[href='/accounts/matches/']").count() > 0)

        # ---------- Phase 4 ----------
        await u.goto(B + "/tools/resume-keyword-scanner/?job=2"); await u.click("#rm-btn"); await u.wait_for_selector("#rm-results", state="visible")
        ok("P4.1 tailor card visible with free tailor", "1 free tailor" in await u.inner_text("#rm-tailor-quota"))
        await u.click("#rm-tailor-btn"); await u.wait_for_selector("#rm-review", state="visible", timeout=30000)
        chg = await u.locator(".rm-chg").count(); ok("P4.2 review shows before/after changes", chg >= 1, f"{chg} changes")
        _evs = await u.evaluate("JSON.stringify(dataLayer.map(e=>e.event))")
        ok("T3 tailor_click + tailor_success tracked", "tailor_click" in _evs and "tailor_success" in _evs)
        ok("P4.3 'we did not add' honesty note", "did not add" in (await u.inner_text("#rm-notadded")).lower())
        ok("P4.4 quota now used", "used" in (await u.inner_text("#rm-tailor-quota")).lower())
        await u.locator(".rm-chg input").first.uncheck()
        async with u.expect_download() as dl:
            await u.click("#rm-docx")
        path = await (await dl.value).path()
        import docx
        d = docx.Document(path); body = "\n".join(p.text for p in d.paragraphs)
        ok("P4.5 downloaded a real Word file", d.paragraphs[0].text == "Jane Doe" and "SUMMARY" in body)
        ok("P4.6 unticked change NOT applied, others applied", "Led: Administered" not in body and "Led: Ran Pardot" in body)
        await u.click("#rm-tailor-btn") if await u.is_visible("#rm-tailor-btn") else None
        await u.wait_for_selector("#rm-pro", state="visible", timeout=10000)
        ok("P4.7 second tailor -> Pro $12 card", "$12/month" in await u.inner_text("#rm-pro"))
        await u.click("#rm-pro-btn")
        await u.wait_for_function("document.getElementById('rm-pro-btn').textContent.indexOf('list')>-1", timeout=20000)
        ok("P4.8 reserve Pro spot works", "on the list" in (await u.inner_text("#rm-pro-btn")).lower())
        evs = await u.evaluate("JSON.stringify(dataLayer.map(e=>e.event))")
        ok("T4 download + Pro gate + Pro click tracked", all(x in evs for x in ["tailor_download", "pro_gate_shown", "pro_preorder_click"]))
        e2 = await newpage(); await e2.goto(B + "/tools/resume-keyword-scanner/"); await e2.click("#rm-btn")
        ok("T5 errors tracked (ats_error_shown)", "ats_error_shown" in await e2.evaluate("JSON.stringify(dataLayer.map(e=>e.event))"))
        a2 = await newpage(); await a2.goto(B + "/tools/resume-keyword-scanner/?job=2"); await a2.click("#rm-paste-toggle"); await a2.fill("#rm-resume", RES_TXT)
        await a2.click("#rm-btn"); await a2.wait_for_selector("#rm-results", state="visible")
        ok("P4.9 anonymous sees 'create account to tailor'", await a2.is_visible("#rm-tailor-signup"))
        mm = await newpage(390, 844); await login(mm, "limit@example.com")
        await mm.goto(B + "/tools/resume-keyword-scanner/?job=2"); await mm.click("#rm-paste-toggle"); await mm.fill("#rm-resume", RES_TXT)
        await mm.click("#rm-btn"); await mm.wait_for_selector("#rm-results", state="visible")
        await mm.click("#rm-tailor-btn"); await mm.wait_for_selector("#rm-review", state="visible", timeout=30000)
        ok("P4.10 tailor review fits mobile", await mm.evaluate("document.documentElement.scrollWidth") <= 390)
        await u.screenshot(path="tailor_desktop.png", full_page=True); await mm.screenshot(path="tailor_mobile.png", full_page=True)

        ok("Z JS errors none", not errs, errs[:3])
        print(f"\n{sum(1 for r in R if r[1])}/{len(R)} passed")
        await b.close()

asyncio.run(main())
