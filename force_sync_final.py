import os
import django
from django.db import connection

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def force_sync():
    print("🚑 STARTING EMERGENCY DATABASE RECOVERY...")
    
    # List of all missing columns detected from your errors
    cols_to_add = [
        ("is_featured", "boolean DEFAULT false"),
        ("is_pinned", "boolean DEFAULT false"),
        ("plan_name", "varchar(50)"),
        ("screening_details", "jsonb DEFAULT '{}'"),
        ("screening_score", "double precision"),
        ("screening_reason", "text"),
        ("screened_at", "timestamp with time zone"),
        ("work_arrangement", "varchar(10) DEFAULT 'onsite'")
    ]
    
    with connection.cursor() as cursor:
        # Check current state of the table
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job';")
        existing_cols = [row[0] for row in cursor.fetchall()]
        print(f"📋 Found existing columns: {existing_cols}")

        for col, definition in cols_to_add:
            if col not in existing_cols:
                print(f"🛠️ Column '{col}' is missing. Adding it now...")
                try:
                    cursor.execute(f"ALTER TABLE jobs_job ADD COLUMN {col} {definition};")
                    print(f"✅ Successfully added '{col}'.")
                except Exception as e:
                    print(f"❌ Failed to add '{col}': {e}")
            else:
                print(f"✅ Column '{col}' already exists.")

if __name__ == '__main__':
    try:
        force_sync()
        print("\n🚀 DATABASE PHYSICALLY SYNCED. Refresh your website now.")
    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
