#!/bin/sh
set -e

echo "==> Waiting for PostgreSQL to become available..."
python << 'PYEOF'
import os, sys, time
import psycopg2

retries = 30
for attempt in range(1, retries + 1):
    try:
        conn = psycopg2.connect(
            dbname=os.environ.get("POSTGRES_DB", "promo_orders"),
            user=os.environ.get("POSTGRES_USER", "postgres"),
            password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
            host=os.environ.get("POSTGRES_HOST", "db"),
            port=os.environ.get("POSTGRES_PORT", "5432"),
        )
        conn.close()
        print(f"PostgreSQL is ready (attempt {attempt}).")
        sys.exit(0)
    except psycopg2.OperationalError:
        print(f"Attempt {attempt}/{retries}: not ready yet, retrying in 2s...")
        time.sleep(2)

print("PostgreSQL did not become available in time. Aborting.")
sys.exit(1)
PYEOF

echo "==> Applying database migrations..."
python manage.py migrate --noinput

echo "==> Starting application..."
exec "$@"
