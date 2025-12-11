import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_database():
    print("🔍 Inspecting Database Schema for 'jobs_job' table...")
    
    with connection.cursor() as cursor:
        # 1. Get list of actual columns in the database
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job';")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Current Database Columns: {columns}")

        # 2. Check and Add 'salary_range'
        if 'salary_range' not in columns:
            print("🛠️ 'salary_range' is MISSING. Adding it now...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN salary_range varchar(100);")
            print("✅ Added 'salary_range'.")
        else:
            print("✅ 'salary_range' already exists.")

        # 3. Check and Add 'tags'
        if 'tags' not in columns:
            print("🛠️ 'tags' is MISSING. Adding it now...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN tags varchar(200);")
            print("✅ Added 'tags'.")
        else:
            print("✅ 'tags' already exists.")

        # 4. Check and Add 'company_logo' (just to be safe)
        if 'company_logo' not in columns:
            print("🛠️ 'company_logo' is MISSING. Adding it now...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN company_logo varchar(200);")
            print("✅ Added 'company_logo'.")
        else:
            print("✅ 'company_logo' already exists.")

    print("\n🚀 REPAIR COMPLETE. You can now reload your website.")

if __name__ == '__main__':
    fix_database()
