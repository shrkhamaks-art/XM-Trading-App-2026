"""Runs all Alembic migrations against a disposable SQLite database."""
import os
import subprocess
import sys
from pathlib import Path
from sqlalchemy import create_engine, inspect, text

def test_alembic_upgrade_head(tmp_path):
    backend = Path(__file__).resolve().parents[1]
    dbfile = tmp_path / 'migrations.sqlite'
    env = dict(os.environ, DATABASE_URL=f'sqlite:///{dbfile}', APP_ENV='development')
    result = subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=backend, env=env, text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(env['DATABASE_URL'])
    tables = set(inspect(engine).get_table_names())
    assert {'users','auth_sessions','ledger_accounts','ledger_transactions','ledger_entries','alembic_version'} <= tables
    with engine.connect() as connection:
        assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one() == '0004_ledger_hash'
    engine.dispose()
