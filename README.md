matcha-inventory-system
Inventory management system I built for Botaniks, a small matcha manufacturing company in Santa Cruz. They were tracking everything — raw materials, production batches, shipments — mentally. I proposed building something to fix it, and it's been running in production since early 2025. My employer now allocates paid hours for me to keep developing it.
Live: https://botanik-inventory-system.onrender.com (currently only accessible to Botaniks) 

What it does

Track raw materials with stock levels, reorder thresholds, and supplier info
Create production batches — pulls from a recipe, deducts materials automatically, rolls back on failure
Mark batches as shipped, keep a log of shipped history
Full CRUD for recipes (web + CLI)
Low-stock alerts, Excel exports for everything
Nightly automated backups via GitHub Actions → Supabase Storage

Stack

Backend: Python / Flask / Gunicorn
Database: PostgreSQL (Supabase in prod, SQLite locally)
Hosting: Render
Backups: GitHub Actions running pg_dump nightly, stored as .sql files in Supabase Storage

How the code is organized
app.py              # Flask routes, auth, form handling
inventory_app.py    # all the actual business logic and DB operations
database.py         # abstraction layer so SQLite and PostgreSQL are interchangeable
cli.py              # command-line interface (alternative to the web app)
helper_functions.py # input validation, exports, backup utilities
init_db.py          # schema setup for fresh PostgreSQL deployments
backup_prod.py      # production backup script
The database.py wrapper handles the SQLite (?) vs PostgreSQL (%s) parameter difference and last-insert-id differences automatically, so there are zero code changes between environments. Web routes and CLI functions share the same business logic layer but are kept separate so CLI workflows don't break when the web app changes.
Running locally
bashgit clone https://github.com/aerogreenfield/matcha-inventory-system
cd matcha-inventory-system
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
.env:
DATABASE_URL=          # leave blank to use SQLite locally
AUTH_USERNAME=
AUTH_PASSWORD=
bashpython app.py    # web app → localhost:8000
python cli.py    # CLI
Backups
Automated nightly at 2am UTC. Files land in Supabase Storage under db-backups/ as prod_backup_YYYYMMDD_HHMMSS.sql.
To restore:
bashpsql "your-DATABASE_URL" < prod_backup_YYYYMMDD_HHMMSS.sql
See backup_instructions.txt for the full walkthrough.


Built by Aero Greenfield while studying Technology & Information Management at UC Santa Cruz.
