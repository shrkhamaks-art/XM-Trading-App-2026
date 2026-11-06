# Phase 09 execution report — 2026-11-05

## Changes performed in this continuation
- Inspected the existing Phase 09 incremental archive and retained its project tree.
- Hardened OTP: development codes are disabled by default; local-only demo requires explicit `ALLOW_DEV_OTP=true`.
- Production settings now reject `ALLOW_DEV_OTP=true`.
- Added configuration regression tests in `backend/tests/test_configuration.py`.

## Execution evidence and limitations
- Python compilation: run separately and report its actual exit code.
- Pytest: run separately; missing `python-jose` and `psycopg` in this environment prevent normal suite execution.
- Attempted pip install of pinned packages; network DNS unavailable, so installation failed.
- No live PostgreSQL instance or Android SDK / signing key was supplied. No database migration, APK, AAB, or real provider test was completed.
- Existing demo OTP behavior is NOT a real delivery service and MUST NOT be enabled on a public server.
- Trading, withdrawals and deposits remain disabled; ledger schema is not a verified accounting system.

## Reproduction commands (trusted developer machine)
```bash
cd backend
python -m pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost:5432/xm'
export JWT_SECRET='replace-with-a-secret-of-at-least-32-bytes'
export OTP_PEPPER='replace-with-an-independent-secret-of-at-least-32-bytes'
export APP_ENV=development
export ALLOW_DEV_OTP=true # ONLY for isolated local testing
alembic upgrade head
PYTHONPATH=. pytest -q tests
```
Never enable `ALLOW_DEV_OTP` in production. Configure a contracted real OTP provider before deploying registration.
