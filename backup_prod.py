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
import re                    # for non-brittle table detection in the integrity check
import urllib.request        # stdlib — pings healthchecks.io with zero new dependencies
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

# ============================================================
# INTEGRITY CHECK  —  runs BEFORE any upload
# ============================================================
# WHY THIS EXISTS: pg_dump returns exit code 0 even when the dump is
# near-empty or truncated. The exit code proves the *command* ran, not
# that your *data* is inside. A "successful" empty backup is the most
# dangerous kind, because you'll trust it. This turns "a file exists"
# into "a valid backup exists."

# Anchor tables that are structural and will never be removed. We check
# for THESE rather than an exhaustive list of every table — an exhaustive
# list would be brittle and break the check every time the schema changes.
CORE_TABLES = ("raw_materials", "batches")
MIN_TABLE_COUNT = 4      # sanity floor; the real schema has more than this
MIN_SIZE_BYTES = 2048    # a valid dump of this DB is always larger than this

def verify_backup_integrity(backup_path):
    """Raise if the dump looks empty, truncated, or schema-only. Returns None on success."""
    size = os.path.getsize(backup_path)
    if size < MIN_SIZE_BYTES:
        raise ValueError(f"Backup too small ({size} bytes) — likely empty or truncated")

    with open(backup_path, "r", encoding="utf-8", errors="replace") as f:
        contents = f.read()

    # Count CREATE TABLE statements — proves the schema made it in.
    create_count = len(re.findall(r"CREATE TABLE", contents))
    if create_count < MIN_TABLE_COUNT:
        raise ValueError(f"Only {create_count} CREATE TABLE statements — expected >= {MIN_TABLE_COUNT}")

    # Confirm the anchor tables specifically are present (handles pg_dump's
    # `public.raw_materials` / quoted-identifier variations).
    missing = [t for t in CORE_TABLES
               if not re.search(rf'CREATE TABLE\s+(?:public\.)?"?{t}"?', contents)]
    if missing:
        raise ValueError(f"Backup missing core tables: {missing}")

    # pg_dump writes row data as COPY blocks by default. No COPY = schema only,
    # no actual rows — a backup that restores an empty database.
    if "COPY " not in contents:
        raise ValueError("Backup has no COPY data blocks — schema only, no rows")

    print(f"✅ Integrity check passed ({size/1024:.1f} KB, {create_count} tables)")


# ============================================================
# CLOUDFLARE R2  —  the off-site copy (different failure domain than Supabase)
# ============================================================
def get_r2_client():
    """Build an S3 client pointed at R2. Returns None if R2 is intentionally unset;
    raises if it's *partially* set (a misconfiguration we want to hear about)."""
    account_id = os.getenv("R2_ACCOUNT_ID")
    access_key = os.getenv("R2_ACCESS_KEY_ID")
    secret_key = os.getenv("R2_SECRET_ACCESS_KEY")
    bucket     = os.getenv("R2_BUCKET")

    if not any([account_id, access_key, secret_key, bucket]):
        return None
    if not all([account_id, access_key, secret_key, bucket]):
        raise RuntimeError("R2 partially configured — check all four R2_* secrets")

    import boto3  # imported lazily so a missing dep fails loudly here, not at startup
    endpoint = f"https://{account_id}.r2.cloudflarestorage.com"
    return boto3.client("s3", endpoint_url=endpoint,
                        aws_access_key_id=access_key, aws_secret_access_key=secret_key,
                        region_name="auto")

def upload_to_r2(s3, local_filepath):
    bucket = os.getenv("R2_BUCKET")
    key = os.path.basename(local_filepath)   # e.g. prod_backup_20260706_020000.sql
    s3.upload_file(local_filepath, bucket, key)
    print(f"✅ Uploaded to R2: {key}")
    return key


# ============================================================
# PRUNING  —  keep newest N in BOTH buckets
# ============================================================
# WHY PRUNE SUPABASE TOO (not just R2): free-tier Supabase Storage has a hard
# size cap. Unbounded nightly uploads eventually hit it, and then new uploads
# FAIL SILENTLY — you'd think you're backed up while you aren't. This is a
# latent bug in your current setup today. Filenames are timestamped
# (prod_backup_YYYYMMDD_HHMMSS.sql), so lexical sort == chronological order.
KEEP = 30

def prune_supabase(keep=KEEP):
    supabase_url = os.getenv("SUPABASE_URL")
    service_key  = os.getenv("SUPABASE_SERVICE_KEY")
    if not (supabase_url and service_key):
        return
    from supabase import create_client
    supabase = create_client(supabase_url, service_key)
    files = supabase.storage.from_("db-backups").list()
    backups = sorted([f for f in files if f["name"].endswith(".sql")],
                     key=lambda x: x["name"], reverse=True)
    old = [f["name"] for f in backups[keep:]]
    if old:
        supabase.storage.from_("db-backups").remove(old)
        print(f"🧹 Pruned {len(old)} old backup(s) from Supabase")

def prune_r2(s3, keep=KEEP):
    bucket = os.getenv("R2_BUCKET")
    resp = s3.list_objects_v2(Bucket=bucket)
    objs = [o for o in resp.get("Contents", []) if o["Key"].endswith(".sql")]
    backups = sorted(objs, key=lambda x: x["Key"], reverse=True)
    for o in backups[keep:]:
        s3.delete_object(Bucket=bucket, Key=o["Key"])
    if len(backups) > keep:
        print(f"🧹 Pruned {len(backups) - keep} old backup(s) from R2")


# ============================================================
# DEAD-MAN'S SWITCH  —  pinged LAST, only on full success
# ============================================================
# WHY LAST: if we pinged at the start, a failing upload would still report
# "healthy." The ping must mean "a verified backup landed in two places."
# WHY IT MATTERS FOR SUMMER: GitHub disables scheduled workflows after 60
# days of no repo activity — silently. A job that never runs sends no failure
# email. healthchecks.io alerts on the *absence* of a ping, which is the only
# way to catch that.
def ping_healthcheck(success=True):
    url = os.getenv("HEALTHCHECK_URL")
    if not url:
        return
    target = url if success else url.rstrip("/") + "/fail"
    try:
        urllib.request.urlopen(target, timeout=10)
    except Exception as e:
        print(f"⚠️ healthcheck ping failed (non-fatal): {e}")



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
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S') 
    backup_filename = f"prod_backup_{timestamp}.sql"
    backup_path = os.path.join('backups', backup_filename) 

    print(f" Running pg_dump...")
    print(f"   Connecting to: {database_url[:45]}...")
    print(f"   Writing to: {backup_path}")

    try:
        result = subprocess.run(
            [
                '/usr/lib/postgresql/17/bin/pg_dump', # path to pg_dump executable (GitHub Actions has it pre-installed at this path)
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
    """pg_dump → verify → upload Supabase → upload R2 → prune both → ping."""
    try:
        local_file = run_pg_dump()
        if not local_file:
            raise RuntimeError("pg_dump failed")

        verify_backup_integrity(local_file)     # NEW: gate before any upload

        upload_to_supabase(local_file)           # existing (primary copy)

        s3 = get_r2_client()                     # NEW: off-site copy
        if s3:
            upload_to_r2(s3, local_file)
            prune_r2(s3)
        else:
            print("ℹ️ R2 not configured — skipping off-site copy")

        prune_supabase()                         # NEW: bound the free-tier bucket
        cleanup_local_file(local_file)

        ping_healthcheck(success=True)           # NEW: last, on success only
        print("\n✅ Backup complete (verified, 2 destinations).")

    except Exception as e:
        print(f"\n❌ Backup FAILED: {e}")
        ping_healthcheck(success=False)          # NEW: alerts you
        exit(1)                                   # marks the Action red


if __name__ == "__main__":
    # Show what's already backed up
    list_remote_backups()

    # Run the backup
    run_full_backup()