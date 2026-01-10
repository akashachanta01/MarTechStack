import os
import django
from django.db import connection

# Setup Django configuration
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

def fix_duplicates():
    print("🔧 Starting Database Deduplication...")
    
    with connection.cursor() as cursor:
        # 1. Find names that appear more than once
        cursor.execute("""
            SELECT name 
            FROM jobs_tool 
            GROUP BY name 
            HAVING count(*) > 1;
        """)
        duplicate_names = [row[0] for row in cursor.fetchall()]
        
        if not duplicate_names:
            print("   ✅ No duplicates found. Database is clean.")
            return

        print(f"   ⚠️ Found duplicates for: {duplicate_names}")

        for name in duplicate_names:
            # Get all IDs for this tool name
            cursor.execute("SELECT id FROM jobs_tool WHERE name = %s ORDER BY id ASC", [name])
            ids = [row[0] for row in cursor.fetchall()]
            
            # Keeper = First ID (Oldest)
            keeper_id = ids[0]
            # Removers = All other IDs
            remover_ids = ids[1:]
            
            print(f"      Processing '{name}': Keeping ID {keeper_id}, merging {remover_ids}...")

            for remove_id in remover_ids:
                # A. Move Jobs: Point links from the duplicate tool to the keeper tool.
                # The 'WHERE NOT EXISTS' clause prevents crashing if the job already has the keeper tool.
                cursor.execute("""
                    UPDATE jobs_job_tools 
                    SET tool_id = %s 
                    WHERE tool_id = %s 
                    AND job_id NOT IN (
                        SELECT job_id FROM jobs_job_tools WHERE tool_id = %s
                    )
                """, [keeper_id, remove_id, keeper_id])
                
                # B. Delete Remaining Links (The ones that were duplicates)
                cursor.execute("DELETE FROM jobs_job_tools WHERE tool_id = %s", [remove_id])
                
                # C. Delete the Duplicate Tool itself
                cursor.execute("DELETE FROM jobs_tool WHERE id = %s", [remove_id])
                
                print(f"         ↳ Merged & Deleted Tool ID {remove_id}")

    print("✨ Duplicates resolved successfully.")

if __name__ == "__main__":
    fix_duplicates()
