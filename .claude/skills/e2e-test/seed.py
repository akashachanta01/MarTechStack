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
for u in ("jane", "limit"):
    User.objects.filter(username=u).delete()
    User.objects.create_user(u, f"{u}@example.com", "pw12345!x")
print("live jobs:", Job.objects.filter(is_active=True).count())
