"""Runs against PostgreSQL in CI; skipped in SQLite-only local environments."""
import os
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.ledger_service import post_transaction, account_balance

@pytest.mark.skipif(not os.getenv('DATABASE_URL','').startswith('postgresql'),reason='PostgreSQL DATABASE_URL required')
def test_postgres_committed_ledger_and_replay():
    engine=create_engine(os.environ['DATABASE_URL'],pool_pre_ping=True)
    # CI runs Alembic upgrade head before pytest. Keep test records isolated by rollback.
    with engine.begin() as connection:
        assert connection.execute(text('SELECT 1')).scalar_one()==1
        with Session(bind=connection,join_transaction_mode='create_savepoint') as s:
            a=LedgerAccount(code='ci-pg-a-unique',currency='USD')
            b=LedgerAccount(code='ci-pg-b-unique',currency='USD')
            s.add_all([a,b]);s.flush()
            payload=dict(idempotency_key='ci-postgres-ledger-unique-01',reference='ci-pg',currency='USD',lines=[{'account_id':a.id,'debit':'7.25'},{'account_id':b.id,'credit':'7.25'}])
            tx,created=post_transaction(s,**payload)
            assert created and post_transaction(s,**payload)==(tx,False)
            assert account_balance(s,a.id)==Decimal('7.2500')
            s.rollback()
    engine.dispose()
