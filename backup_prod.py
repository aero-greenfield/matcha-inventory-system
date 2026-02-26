"""
Botaniks Production Database Backup Script
============================================

Runs pg_dump against Supabase PostgreSQL, then uploads
the .sql file to Supabase Storage bucket 'db-backups'.

WHEN THIS RUNS:
- Automatically: Every night at 2am UTC via GitHub Actions (backup.yml workflow)
- Manually: python backup_prod.py (from your local machine)
- On-demand: GitHub → Actions → Daily Database Backup → Run workflow

WHERE BACKUPS GO:
- Supabase Dashboard → Storage → db-backups
- Filename format: prod_backup_20260225_020000.sql

RECOVERY:
1. Supabase Dashboard → Storage → db-backups → download the file
2. Run: psql "your-DATABASE_URL" < prod_backup_20260225_020000.sql




CREDENTIALS:
- Local: reads from .env file
- GitHub Actions: reads from GitHub repository secrets
  (injected as environment variables automatically)
"""





import os
import subprocess
from datetime import datetime

# ----------------------------------------
# LOAD ENVIRONMENT VARIABLES
# Works locally (.env file) and on GitHub Actions
# (secrets injected as env vars automatically)
# ----------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # dotenv not available — running in GitHub Actions
    # environment variables already injected by workflow
    pass


def run_pg_dump():
    """
    Runs pg_dump against Supabase PostgreSQL.


    pg_dump connects to live database → generates .sql file locally →  upload that file to Supabase Storage.

    ex:
    DROP TABLE IF EXISTS raw_materials;
        CREATE TABLE raw_materials (...);
        INSERT INTO raw_materials VALUES (...);
        -- repeated for every table and every row


    --clean AND --if-exists:   (because when restoring, there might already be tables in the way)
             -> clean: adds DROP TABLE before each CREATE, so the restore wipes and replaces instead of erroring out.
             -> if-exists: prevents errors if a table doesn't exist yet.

    --no-owner AND --no-privileges: (because Supabase manages its own user permissions internally, 
    and including ownership/privilege statements would cause errors on restore because the users don't match)







    Returns: local filepath of .sql file, or None if failed



    """

    database_url = os.getenv('DATABASE_URL') # get supabase postgres URL from environment variable

    if not database_url:
        print("❌ DATABASE_URL not found in environment")
        print("   Local: check your .env file")
        print("   GitHub Actions: check repository secrets")
        return None

    
    # Supabase gives: postgres://...
    # pg_dump needs: postgresql://...
    database_url = database_url.replace('postgres://', 'postgresql://', 1) #syntax for pg_dump connection string

    # Create local temp folder for the file
    os.makedirs('backups', exist_ok=True) # temp folder for .sql files (will be deleted after upload) 

    # Timestamped filename
    # Example: prod_backup_20260225_020000.sql
    timestamp = datetime.now().strftime('%Y%m%d %H%M%S') 
    backup_filename = f"prod_backup_{timestamp}.sql"
    backup_path = os.path.join('backups', backup_filename) 

    print(f" Running pg_dump...")
    print(f"   Connecting to: {database_url[:45]}...")
    print(f"   Writing to: {backup_path}")

    try:
        result = subprocess.run(
            [
                'pg_dump',
                '--no-password',    # Password is in the URL, don't prompt
                '--clean',          # DROP TABLE before CREATE TABLE
                '--if-exists',      # Safe DROP (no error if table missing)
                '--no-owner',       # Skip ownership commands
                '--no-privileges',  # Skip GRANT/REVOKE
                '--format=plain',   # Plain SQL output
                '--file', backup_path,
                database_url
            ],
            capture_output=True,
            text=True
        )

        if result.returncode == 0: # success
            size_kb = os.path.getsize(backup_path) / 1024 # get file size in KB
            print(f"✅ pg_dump complete ({size_kb:.1f} KB)") 
            return backup_path
        else:
            print(f"❌ pg_dump failed:")
            print(f"   {result.stderr}")
            return None

    except FileNotFoundError:
        print("❌ pg_dump not found on this machine")
        print("   Mac: brew install postgresql")
        print("   Windows: Install PostgreSQL from postgresql.org")
        print("   GitHub Actions: handled by workflow (apt-get install postgresql-client)")
        return None

    except Exception as e:
        print(f"❌ Unexpected error during pg_dump: {e}")
        return None


def upload_to_supabase(local_filepath):
    """
    Uploads .sql file to Supabase Storage bucket 'db-backups'.

    
    SERVICE KEY:
    - anon key is read-only by default
    - service_role key has full read/write storage access
    - Safe here because this script runs server-side only
    - Never put service_role key in frontend browser code

    Returns: filename of uploaded file, or None if failed
    """

    supabase_url = os.getenv('SUPABASE_URL') # get supabase URL from environment variable (same as DATABASE_URL but without the /postgres path)
    service_key = os.getenv('SUPABASE_SERVICE_KEY') # service key with storage permissions, from environment variable

    if not supabase_url or not service_key:
        print("❌ SUPABASE_URL or SUPABASE_SERVICE_KEY not found")
        print("   Local: check your .env file")
        print("   GitHub Actions: check repository secrets")
        return None

    try:
        from supabase import create_client

        # Create Supabase client with service role key
        supabase = create_client(supabase_url, service_key)

        filename = os.path.basename(local_filepath)

        print(f"🔄 Uploading to Supabase Storage...")
        print(f"   Bucket: db-backups")
        print(f"   File: {filename}")

        # Read file as bytes for upload
        with open(local_filepath, 'rb') as f:
            file_data = f.read()

        # Upload to Supabase Storage
        supabase.storage.from_('db-backups').upload(
            path=filename,
            file=file_data,
            file_options={
                "content-type": "application/sql",
                "x-upsert": "false"  # Never overwrite — each backup is unique
            }
        )

        print(f"✅ Upload successful!")
        print(f"   View at: Supabase Dashboard → Storage → db-backups → {filename}")
        return filename

    except Exception as e:
        print(f"❌ Upload failed: {e}")
        return None


def cleanup_local_file(filepath):
    """
    Deletes the local .sql file after successful upload.

    

    If you want to keep local copies, just don't call function.
    """
    try:
        os.remove(filepath)
        print(f"🗑️  Cleaned up local temp file")
    except Exception as e:
        print(f"⚠️  Could not delete local file: {e}")


def list_remote_backups():
    """
    Lists all backups currently in Supabase Storage.

        Useful to see what's already backed up before running a new backup.
    """
    supabase_url = os.getenv('SUPABASE_URL')
    service_key = os.getenv('SUPABASE_SERVICE_KEY')

    if not supabase_url or not service_key:
        return

    try:
        from supabase import create_client
        supabase = create_client(supabase_url, service_key)

        files = supabase.storage.from_('db-backups').list()

        if not files:
            print("📭 No backups found in Supabase Storage yet.")
            return

        print(f"\n{'='*55}")
        print(f"  EXISTING BACKUPS IN SUPABASE ({len(files)} files)")
        print(f"{'='*55}")

        for f in sorted(files, key=lambda x: x['name'], reverse=True):
            size_kb = f.get('metadata', {}).get('size', 0) / 1024
            created = f.get('created_at', 'unknown')[:19]
            print(f"  📄 {f['name']}")
            print(f"     {size_kb:.1f} KB | {created}")

        print()

    except Exception as e:
        print(f"⚠️  Could not list remote backups: {e}")


def run_full_backup():
    """
    Main function: pg_dump → upload → cleanup.

    Called by GitHub Actions workflow every night,
    or manually with: python backup_prod.py
    """

    print("\n" + "="*55)
    print("  BOTANIKS DATABASE BACKUP")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print("="*55 + "\n")

    # Step 1: pg_dump to local .sql file
    local_file = run_pg_dump()
    if not local_file:
        print("\n❌ Backup aborted — pg_dump failed.")
        # Exit with error code so GitHub Actions marks the run as failed
        # You'll get an email notification when this happens
        exit(1)

    # Step 2: Upload to Supabase Storage
    remote_file = upload_to_supabase(local_file)
    if not remote_file:
        print(f"\n⚠️  Upload failed — local file kept at: {local_file}")
        exit(1)

    # Step 3: Clean up local temp file
    cleanup_local_file(local_file)

    print("\n✅ Backup complete.")
    print("   Check: Supabase Dashboard → Storage → db-backups")


if __name__ == "__main__":
    # Show what's already backed up
    list_remote_backups()

    # Run the backup
    run_full_backup()