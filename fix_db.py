import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_database():
    print("🔧 Attempting to clean up database conflicts...")
    with connection.cursor() as cursor:
        try:
            # 1. Drop the ghost table that is blocking migration
            cursor.execute("DROP TABLE IF EXISTS jobs_subscriber CASCADE;")
            print("   ✅ Successfully dropped 'jobs_subscriber' table.")
        except Exception as e:
            print(f"   ⚠️ Error dropping table: {e}")

if __name__ == "__main__":
    fix_database()
