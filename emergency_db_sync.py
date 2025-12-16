import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_database():
    print("🚑 STARTING EMERGENCY DB SYNC...")
    
    with connection.cursor() as cursor:
        # 1. Get list of existing columns
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job';")
        columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Current Columns: {columns}")

        # 2. Add 'remote' if missing
        if 'remote' not in columns:
            print("🛠️ Adding missing column: 'remote'...")
            # Boolean field default false
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN remote boolean DEFAULT false;")
        else:
            print("✅ 'remote' exists.")

        # 3. Add 'role_type' if missing
        if 'role_type' not in columns:
            print("🛠️ Adding missing column: 'role_type'...")
            # Charfield default 'full_time'
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN role_type varchar(20) DEFAULT 'full_time';")
        else:
            print("✅ 'role_type' exists.")

        # 4. Add 'tags' if missing (just in case)
        if 'tags' not in columns:
            print("🛠️ Adding missing column: 'tags'...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN tags varchar(200);")
        else:
            print("✅ 'tags' exists.")

        # 5. Add 'salary_range' if missing
        if 'salary_range' not in columns:
            print("🛠️ Adding missing column: 'salary_range'...")
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN salary_range varchar(100);")
        else:
            print("✅ 'salary_range' exists.")

    print("\n🚀 DB SYNC COMPLETE. Database now matches models.py.")

if __name__ == '__main__':
    fix_database()
