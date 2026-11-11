#!/usr/bin/env bash
# build.sh — Render build script for the CRM service.
#
# Render runs this during every deploy. It:
#   1. Installs Python deps
#   2. Builds the React frontend into frontend/dist/
#   3. Runs Alembic migrations against the live DB
#   4. Seeds the DB if empty (idempotent — skips if data exists)

set -o errexit  # exit on error

# On Render (RENDER=true), catch the two most common setup mistakes early.
if [ "${RENDER:-}" = "true" ]; then
  case "${DATABASE_URL:-}" in
    "")
      echo "ERROR: DATABASE_URL is not set."
      echo "  Render dashboard -> your PostgreSQL database -> copy the 'Internal Database URL'"
      echo "  -> this service -> Environment -> add DATABASE_URL = <that URL> -> Save."
      exit 1 ;;
    *localhost*|*127.0.0.1*)
      echo "ERROR: DATABASE_URL points at localhost (that's your own PC's database, not Render's)."
      echo "  Replace it with your Render database's 'Internal Database URL'."
      exit 1 ;;
  esac
fi

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Installing frontend dependencies..."
cd frontend
npm install
echo "==> Building frontend..."
npm run build
cd ..

echo "==> Running database migrations..."
alembic upgrade head

echo "==> Seeding database (skips if already seeded)..."
python seed.py

echo "==> Build complete!"
