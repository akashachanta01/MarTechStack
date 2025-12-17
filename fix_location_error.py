import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_location_constraint():
    print("🚑 STARTING DATABASE REPAIR FOR 'location'...")
    
    with connection.cursor() as cursor:
        try:
            # This SQL command tells the database: "It is okay for 'location' to be empty."
            print("🛠️ Removing NOT NULL constraint from 'location'...")
            cursor.execute("ALTER TABLE jobs_job ALTER COLUMN location DROP NOT NULL;")
            print("✅ SUCCESS: 'location' column now accepts NULL values.")
        except Exception as e:
            print(f"❌ Error during repair: {e}")

if __name__ == '__main__':
    fix_location_constraint()
