import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_column():
    print("🚑 STARTING DATABASE REPAIR FOR 'updated_at'...")
    
    with connection.cursor() as cursor:
        # 1. Check if the column exists
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job' AND column_name = 'updated_at';")
        exists = cursor.fetchone()

        if not exists:
            print("🛠️ Column 'updated_at' is MISSING. Adding it now...")
            # Add the column with a default value of NOW() so existing rows aren't empty
            cursor.execute("ALTER TABLE jobs_job ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();")
            print("✅ SUCCESS: Added 'updated_at' column.")
        else:
            print("✅ Column 'updated_at' already exists. No action needed.")

if __name__ == '__main__':
    fix_column()
