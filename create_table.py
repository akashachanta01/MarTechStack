import os
import django
from django.db import connection

# 1. Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def create_table():
    print("--- 🛠️ MANUALLY CREATING SUBSCRIBER TABLE ---")
    
    # SQL to create the table if it's missing
    sql = """
    CREATE TABLE IF NOT EXISTS jobs_subscriber (
        id SERIAL PRIMARY KEY,
        email VARCHAR(254) NOT NULL UNIQUE,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL
    );
    """
    
    with connection.cursor() as cursor:
        try:
            print("Executing SQL...")
            cursor.execute(sql)
            print("✅ SUCCESS: Table 'jobs_subscriber' created.")
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == '__main__':
    create_table()
