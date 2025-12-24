import os
import django
from django.db import connection

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_ghost_columns():
    print("👻 STARTING GHOST COLUMN REPAIR...")
    
    # 1. List of all columns we expect in the Model now
    # (Column Name, SQL Definition)
    expected_columns = [
        ("updated_at", "TIMESTAMP WITH TIME ZONE DEFAULT NOW()"),
        ("tags", "VARCHAR(200)"),
        ("slug", "VARCHAR(250)"),
        ("salary_range", "VARCHAR(100)"),
        ("role_type", "VARCHAR(20) DEFAULT 'full_time'"),
        ("work_arrangement", "VARCHAR(10) DEFAULT 'onsite'"),
        ("is_featured", "BOOLEAN DEFAULT FALSE"),
        ("is_pinned", "BOOLEAN DEFAULT FALSE"),
        ("plan_name", "VARCHAR(50)"),
        ("screening_score", "DOUBLE PRECISION"),
        ("screening_reason", "TEXT"),
        ("screening_details", "JSONB DEFAULT '{}'"),
        ("screened_at", "TIMESTAMP WITH TIME ZONE"),
    ]

    with connection.cursor() as cursor:
        # Get current columns in DB
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'jobs_job';")
        existing_columns = [row[0] for row in cursor.fetchall()]
        print(f"📋 Found {len(existing_columns)} existing columns.")

        for col_name, sql_def in expected_columns:
            if col_name not in existing_columns:
                print(f"🛠️  MISSING: '{col_name}'. Adding it now...")
                try:
                    cursor.execute(f"ALTER TABLE jobs_job ADD COLUMN {col_name} {sql_def};")
                    print(f"   ✅ Success: Added '{col_name}'")
                except Exception as e:
                    print(f"   ❌ Failed to add '{col_name}': {e}")
            else:
                print(f"   ✅ OK: '{col_name}' exists.")

    print("\n🏁 REPAIR COMPLETE. Try refreshing your Admin panel.")

if __name__ == '__main__':
    fix_ghost_columns()
