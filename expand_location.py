import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def run():
    print("🛠️  EXPANDING 'location' COLUMN SIZE...")
    
    with connection.cursor() as cursor:
        try:
            # Change limit from 100 to 255 characters
            cursor.execute("ALTER TABLE jobs_job ALTER COLUMN location TYPE varchar(255);")
            print("✅ Success! Column 'location' can now hold 255 characters.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    run()
