import os
import django

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from jobs.models import Job

def wipe_jobs():
    count = Job.objects.count()
    print(f"⚠️  WARNING: About to delete {count} jobs from the database.")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() == 'yes':
        Job.objects.all().delete()
        print(f"✅ Deleted {count} jobs. Database is clean.")
    else:
        print("❌ Operation cancelled.")

if __name__ == '__main__':
    wipe_jobs()
