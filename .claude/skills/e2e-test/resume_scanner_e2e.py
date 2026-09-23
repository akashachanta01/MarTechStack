"""Resume Scanner E2E (41 scenarios). Needs the seeded server on :8765 (see SKILL.md).
Run from a scratch dir: python /path/to/resume_scanner_e2e.py"""
import asyncio, glob, json, time
from playwright.async_api import async_playwright
B="http://127.0.0.1:8765"; R=[]
def ok(name, cond, info=""): R.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL ")+name+(" — "+str(info) if info else ""))
RES_TXT="Senior Marketing Ops Specialist\n- Administered Marketo; built lead score model lifting MQL-to-SQL conversion 22%\n- Ran Pardot nurture campaigns for 40k contacts across three regions\n- Managed SFMC email sends and journeys for the global team\n- Partnered with sales on routing rules and pipeline reporting\n- Owned Salesforce attribution dashboards for 5 regions"
XSS=RES_TXT+"\n<img src=x onerror=alert(1)> <script>alert(2)</script>"
JD_OK="We need a Marketing Operations Manager to run Marketo, Salesforce and HubSpot, build lead scoring, lead routing and attribution reporting with SQL. "*3
JD_NON="We need a friendly cashier for our downtown sandwich store on weekends and some evenings, handling cash and greeting customers. "*2
async def check(pg, wait_results=True):
    t=time.time(); await pg.click("#rm-btn")
    await pg.wait_for_function("document.getElementById('rm-btn').textContent.indexOf('Checking')<0", timeout=40000)
    return time.time()-t
async def err(pg): return (await pg.inner_text("#rm-err")) if await pg.is_visible("#rm-err") else ""
def make_fixtures():
    """Self-contained test files (run from any folder; files land in cwd)."""
    import docx
    d = docx.Document()
    for l in RES_TXT.splitlines(): d.add_paragraph(l)
    d.save("resume.docx")
    open("bad.txt", "w").write("hello " * 100)
    open("big.pdf", "wb").write(b"%PDF-1.4\n" + b"0" * (6 * 1024 * 1024))
    open("corrupt.pdf", "wb").write(b"%PDF-1.4 garbage not a real pdf")

async def main():
    make_fixtures()
    async with async_playwright() as p:
        exe=(glob.glob('/opt/pw-browsers/chromium-*/chrome-linux/chrome') or glob.glob('/opt/pw-browsers/**/chrome',recursive=True))[0]
        b=await p.chromium.launch(executable_path=exe); errs=[]; alerts=[]
        t=await b.new_page(); await t.set_content("<pre>"+RES_TXT+"</pre>"); await t.pdf(path="resume.pdf"); await t.close()
        async def newpage(w=1280,h=900):
            c=await b.new_context(viewport={"width":w,"height":h}); pg=await c.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e))); pg.on("dialog", lambda d: (alerts.append(d.message), asyncio.ensure_future(d.accept())))
            return pg
        # ===== ANONYMOUS =====
        pg=await newpage()
        r=await pg.goto(B+"/tools/resume-keyword-scanner/?job=1"); ok("A1 page loads with job", r.status==200 and "Marketing Operations Manager" in await pg.inner_text(".rm-job"))
        st=await pg.inner_text(".rm-stats"); ok("A2 real stats shown", "192" in st, st.replace("\n"," "))
        ok("A3 nav says Resume Scanner", await pg.is_visible("a.tools-link:has-text('Resume Scanner')"))
        await pg.click("#rm-btn"); await pg.wait_for_timeout(300); ok("A4 no resume -> clear error", "Upload your resume" in await err(pg), await err(pg))
        for f,expect,label in [("bad.txt","PDF or Word","A5 .txt rejected"),("big.pdf","over 5 MB","A6 >5MB rejected"),("corrupt.pdf","couldn't read","A7 corrupt PDF handled")]:
            await pg.set_input_files("#rm-file",f); await pg.wait_for_timeout(1200); e=await err(pg); ok(label, expect.lower() in e.lower(), e)
        await pg.set_input_files("#rm-file","resume.pdf"); await pg.wait_for_selector("#rm-ok",state="visible")
        ok("A8 PDF upload read (anon, not saved)", "Ready to check" in await pg.inner_text("#rm-ok"))
        secs=await check(pg); e=await err(pg)
        ok("A9 first check from COLD cache succeeds, no timeout", not e and await pg.is_visible("#rm-results"), f"{secs:.1f}s {e}")
        ok("A10 score + label render", "/" in await pg.inner_text("#rm-num") and await pg.inner_text("#rm-lbl"))
        ok("A11 missing list rendered", await pg.locator(".rm-gap").count()>0)
        ok("A12 anon: wording fixes locked + signup CTA", "Create a free account" in await pg.inner_text("#rm-fixes") and await pg.is_visible("#rm-anon-cta"))
        ok("A13 anon: no 'more matches' box", await pg.is_hidden("#rm-more"))
        dl=await pg.evaluate("JSON.stringify(dataLayer.filter(e=>e.event&&e.event.indexOf('ats')==0||e.event==='resume_uploaded').map(e=>e.event))")
        ok("A14 tracking events fired", "ats_check_result" in dl and "resume_uploaded" in dl, dl)
        await check(pg); e=await err(pg); ok("A15 2nd anon check -> signup gate", "Create a free account" in e or "Create free account" in e, e)
        # anon paste + no-job pasted JD paths (fresh session)
        pg2=await newpage(); await pg2.goto(B+"/tools/resume-keyword-scanner/")
        ok("A16 no-job page shows JD box", await pg2.is_visible("#rm-jd"))
        await pg2.click("#rm-paste-toggle"); await pg2.fill("#rm-resume",RES_TXT); await pg2.fill("#rm-jd","too short")
        await check(pg2); ok("A17 short JD -> error", "job description" in (await err(pg2)).lower(), await err(pg2))
        await pg2.fill("#rm-jd",JD_NON); await check(pg2); ok("A18 non-MarTech JD -> friendly 422", "MarTech" in await err(pg2), await err(pg2))
        pg3=await newpage(); await pg3.goto(B+"/tools/resume-keyword-scanner/"); await pg3.click("#rm-paste-toggle")
        await pg3.fill("#rm-resume",XSS); await pg3.fill("#rm-jd",JD_OK); await check(pg3)
        ok("A19 pasted resume + pasted JD works", await pg3.is_visible("#rm-results"), await err(pg3))
        ok("A20 XSS in resume not executed", not alerts, alerts)
        r=await pg3.goto(B+"/tools/resume-keyword-scanner/?job=3"); ok("A21 closed job -> falls back to paste JD", await pg3.is_visible("#rm-jd"))
        r=await pg3.goto(B+"/tools/resume-keyword-scanner/?job=abc"); ok("A22 junk job id -> no crash", r.status==200)
        # job page CTA
        r=await pg3.goto(B+"/job/1/marketing-operations-manager-at-acme/")
        href=await pg3.get_attribute(".js-check-resume[data-placement=top]","href"); ok("A23 job page CTA links to scanner with job", href and "job=1" in href, href)
        # ===== SIGNED IN =====
        u=await newpage()
        await u.goto(B+"/accounts/login/"); await u.fill("input[name=login]","jane@example.com"); await u.fill("input[name=password]","pw12345!x"); await u.click("form button[type=submit]"); await u.wait_for_timeout(900)
        await u.goto(B+"/tools/resume-keyword-scanner/?job=1")
        ok("S1 no saved resume initially", await u.is_hidden("#rm-saved"))
        await u.set_input_files("#rm-file","resume.docx"); await u.wait_for_selector("#rm-saved",state="visible")
        ok("S2 DOCX upload saved to account", "Saved to your account" in await u.inner_text("#rm-ok"))
        await check(u); ok("S3 check with saved resume", await u.is_visible("#rm-results"), await err(u))
        ok("S4 wording fixes shown to members", "You wrote" in await u.inner_text("#rm-fixes"))
        ok("S5 more jobs you match shown", await u.is_visible("#rm-more") and await u.locator(".rm-mjob").count()==3)
        ok("S6 demand % shown once warm", "% of live MarTech jobs" in await u.inner_text("#rm-missing"))
        await u.goto(B+"/tools/resume-keyword-scanner/?job=2"); ok("S7 saved resume remembered on reload", await u.is_visible("#rm-saved"))
        await u.click("#rm-replace"); ok("S8 replace shows upload again", await u.is_visible("#rm-drop"))
        await u.goto(B+"/tools/resume-keyword-scanner/?job=2")
        await u.click("#rm-delete"); await u.wait_for_timeout(700); ok("S9 delete on page", await u.is_hidden("#rm-saved") and "Deleted" in await u.inner_text("#rm-ok"))
        await u.click("#rm-paste-toggle"); await u.fill("#rm-resume",RES_TXT); await u.uncheck("#rm-save"); await check(u)
        await u.goto(B+"/tools/resume-keyword-scanner/?job=2"); ok("S10 paste w/o save -> not saved", await u.is_hidden("#rm-saved"))
        await u.click("#rm-paste-toggle"); await u.fill("#rm-resume",RES_TXT); await check(u)
        await u.goto(B+"/tools/resume-keyword-scanner/?job=2"); ok("S11 paste with save -> saved", await u.is_visible("#rm-saved"))
        await u.goto(B+"/accounts/settings/"); ok("S12 settings shows resume", "Pasted resume" in await u.inner_text("#st-resume-row"))
        await u.click("#st-resume-del"); await u.wait_for_timeout(700); ok("S13 settings delete", "deleted" in (await u.inner_text("#st-resume-row")).lower())
        # monthly limit (5 free checks) with fresh user
        l=await newpage(); await l.goto(B+"/accounts/login/"); await l.fill("input[name=login]","limit@example.com"); await l.fill("input[name=password]","pw12345!x"); await l.click("form button[type=submit]"); await l.wait_for_timeout(900)
        await l.goto(B+"/tools/resume-keyword-scanner/?job=1"); await l.click("#rm-paste-toggle"); await l.fill("#rm-resume",RES_TXT); await l.uncheck("#rm-save")
        for i in range(5): await check(l)
        ok("S14 5 checks allowed", await l.is_visible("#rm-results"))
        await check(l); ok("S15 6th check -> monthly limit message", "5 free checks" in await err(l), await err(l))
        # ===== MOBILE =====
        m=await newpage(390,844); await m.goto(B+"/tools/resume-keyword-scanner/?job=1")
        ok("M1 no horizontal scroll (page)", await m.evaluate("document.documentElement.scrollWidth")<=390)
        await m.set_input_files("#rm-file","resume.pdf"); await m.wait_for_selector("#rm-ok",state="visible"); await check(m)
        ok("M2 results on mobile, no horizontal scroll", await m.is_visible("#rm-results") and await m.evaluate("document.documentElement.scrollWidth")<=390)
        await m.screenshot(path="m_results.png", full_page=True)
        ok("Z JS errors none", not errs, errs[:3])
        print(f"\n{sum(1 for r in R if r[1])}/{len(R)} passed")
        await b.close()
asyncio.run(main())
