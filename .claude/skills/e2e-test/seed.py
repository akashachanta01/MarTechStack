"""Seed a production-sized local DB: ~190 live jobs with full-length JDs + test users.
Run: DEBUG=True SECRET_KEY=x PYTHONPATH=.claude/skills/e2e-test:. DJANGO_SETTINGS_MODULE=test_settings python .claude/skills/e2e-test/seed.py"""
import django
django.setup()
from django.contrib.auth.models import User
from jobs.models import Job

JD = "<p>" + ("Marketing Operations Manager. Own our Marketo Engage instance and Salesforce Marketing Cloud. "
              "Build lead scoring and lead routing, manage nurture streams. Experience with Segment or a customer "
              "data platform. HubSpot, Braze, SQL, attribution. " * 25) + "</p>"
Job.objects.all().delete()
Job.objects.create(title="Marketing Operations Manager", company="Acme", location="Remote", description=JD,
                   apply_url="https://x.test", screening_status="approved", is_active=True, work_arrangement="remote")
Job.objects.create(title="Marketo Administrator", company="Globex", location="Remote", description=JD,
                   apply_url="https://x.test", screening_status="approved", is_active=True, work_arrangement="remote")
Job.objects.create(title="Closed role", company="Initech", location="Remote", description=JD,
                   apply_url="https://x.test", screening_status="rejected", is_active=False, work_arrangement="remote")
Job.objects.bulk_create([Job(title=f"Role {i}", company=f"Co{i % 60}", location="Remote", description=JD,
                             apply_url="https://x.test", screening_status="approved", is_active=True,
                             work_arrangement="remote", slug=f"role-{i}") for i in range(190)])
ADOBE = ("<p>Senior Technical Consultant, Customer Journeys. You will own Adobe Journey Optimizer programs end to end.</p>"
         "<ul><li>Hands-on experience with Adobe Experience Platform and a customer data platform.</li>"
         "<li>Adobe Experience Manager knowledge.</li><li>Marketo Certified Expert is a plus.</li></ul>")
Job.objects.create(title="Senior Technical Consultant - Customer Journeys", company="Adobe", location="Remote",
                   description=ADOBE, apply_url="https://x.test", screening_status="approved", is_active=True,
                   work_arrangement="remote", slug="adobe-consultant")
Job.objects.create(title="Marketo & SFMC Specialist", company="Umbrella", location="Remote",
                   description="<p>Run our Marketo instance and Salesforce Marketing Cloud. Build lead scoring and nurture programs; Pardot migration experience.</p>",
                   apply_url="https://x.test", screening_status="approved", is_active=True, work_arrangement="remote",
                   slug="best-fit-specialist")
# Tools (tool pages + tool job alerts) and enough same-title roles for a
# publishable resume-keywords page.
from jobs.models import Category, Tool
cat, _ = Category.objects.get_or_create(name="MarTech", defaults={"slug": "martech"})
marketo, _ = Tool.objects.get_or_create(name="Marketo", defaults={"slug": "marketo", "category": cat})
hubspot, _ = Tool.objects.get_or_create(name="HubSpot", defaults={"slug": "hubspot", "category": cat})
for j in Job.objects.filter(slug__startswith="role-")[:120]:
    j.tools.add(marketo, hubspot)
Job.objects.filter(title="Marketing Operations Manager").first().tools.add(marketo)
for i, j in enumerate(Job.objects.filter(slug__startswith="role-").order_by("id")[:9]):
    Job.objects.filter(pk=j.pk).update(title=f"Marketing Operations Manager {i + 2}")
# Titles that form generated role pages: 6 Salesforce Developers at 3 employers,
# 3 SFMC Developers at 2 employers (tool x function page), 1 off-topic welder.
SFDEV = "<p>Salesforce developer: Apex, Lightning, integrations with Salesforce Marketing Cloud.</p>"
for i, co in enumerate(["Initech", "Hooli", "Vandelay", "Initech", "Hooli", "Vandelay"]):
    Job.objects.create(title=f"Senior Salesforce Developer {'I' * (i % 2 + 1)}", company=co, location="Remote",
                       description=SFDEV, apply_url="https://x.test", screening_status="approved", is_active=True,
                       work_arrangement="remote", slug=f"sf-dev-{i}")
for i, co in enumerate(["Initech", "Hooli", "Initech"]):
    Job.objects.create(title=f"SFMC Developer {i + 1}", company=co, location="Remote",
                       description="<p>Salesforce Marketing Cloud developer. AMPscript, Journey Builder.</p>",
                       apply_url="https://x.test", screening_status="approved", is_active=True,
                       work_arrangement="remote", slug=f"sfmc-dev-{i}")
Job.objects.create(title="Welder/Brazer II - 2nd Shift (Onsite)", company="Globex", location="Ohio",
                   description="<p>Welding.</p>", apply_url="https://x.test", screening_status="approved",
                   is_active=True, work_arrangement="onsite", slug="welder")
from django.core.management import call_command
call_command("clean_job_data")
for u in ("jane", "limit"):
    User.objects.filter(username=u).delete()
    User.objects.create_user(u, f"{u}@example.com", "pw12345!x")
print("live jobs:", Job.objects.filter(is_active=True).count())
