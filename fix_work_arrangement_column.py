import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_column():
    print("🛠️ FORCING ADDITION OF 'work_arrangement' COLUMN...")
    
    with connection.cursor() as cursor:
        # 1. Check if the column exists
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job' AND column_name = 'work_arrangement';")
        exists = cursor.fetchone()

        if not exists:
            print("❌ Column 'work_arrangement' is MISSING. Adding it now...")
            # SQL command to add the column, matching the model definition (CharField max_length=10, default='onsite')
            # NOT NULL is necessary because we provide a default value.
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN work_arrangement varchar(10) NOT NULL DEFAULT 'onsite';")
            print("✅ SUCCESS: 'work_arrangement' column added with default value 'onsite'.")
        else:
            print("✅ Column 'work_arrangement' already exists.")

if __name__ == '__main__':
    try:
        fix_column()
        print("\n🚀 DATABASE MANUAL FIX COMPLETE. Running final migrate to sync history...")
        # Now that the column exists, run migrate to sync history and apply any other changes
        os.system("python manage.py migrate")
    except Exception as e:
        print(f"❌ CRITICAL ERROR DURING FIX: {e}")
