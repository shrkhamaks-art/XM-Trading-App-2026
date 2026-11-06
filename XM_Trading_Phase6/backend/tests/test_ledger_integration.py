"""Integration checks on temporary SQLite only; not a substitute for PostgreSQL concurrency tests."""
from decimal import Decimal
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from app.db import Base
from app.models import LedgerAccount, LedgerTransaction, LedgerEntry
from app.ledger_service import post_transaction, account_balance
from app.ledger_rules import LedgerValidationError
import pytest

@pytest.fixture
def engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'ledger.db'}")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([LedgerAccount(id=11, code='sandbox-asset', currency='USD'), LedgerAccount(id=12, code='sandbox-offset', currency='USD')])
        s.commit()
    yield engine
    engine.dispose()

def payload(key='sandbox-key-00001', amount='15.2500'):
    return dict(idempotency_key=key, reference='sandbox-reference', currency='USD', lines=[{'account_id':11,'debit':amount},{'account_id':12,'credit':amount}])

def test_persistence_across_sessions_and_idempotency(engine):
    with Session(engine) as s:
        tx, created = post_transaction(s, **payload())
        assert created
        s.commit()
    with Session(engine) as s:
        assert post_transaction(s, **payload()) == (tx, False)
        assert account_balance(s, 11) == Decimal('15.2500')
        assert account_balance(s, 12) == Decimal('-15.2500')
        assert s.query(LedgerEntry).count() == 2

def test_rollback_leaves_no_financial_records(engine):
    with engine.connect() as connection:
        # SQLite's driver needs an explicit BEGIN before the SAVEPOINT.
        connection.exec_driver_sql('BEGIN')
        with Session(bind=connection) as s:
            post_transaction(s, **payload('sandbox-key-rollback'))
            s.flush()
        connection.rollback()
    with Session(engine) as s:
        assert s.query(LedgerTransaction).count() == 0
        assert s.query(LedgerEntry).count() == 0

def test_conflicting_replay_does_not_change_balances(engine):
    with Session(engine) as s:
        post_transaction(s, **payload()); s.commit()
    with Session(engine) as s:
        with pytest.raises(LedgerValidationError):
            post_transaction(s, **payload(amount='16.0000'))
        s.rollback()
    with Session(engine) as s:
        assert s.query(LedgerTransaction).count() == 1
        assert account_balance(s, 11) == Decimal('15.2500')

def test_multi_currency_account_rejected(engine):
    with Session(engine) as s:
        s.add(LedgerAccount(id=13, code='sandbox-eur', currency='EUR')); s.commit()
        with pytest.raises(LedgerValidationError):
            post_transaction(s, idempotency_key='sandbox-mismatch-01', reference='test', currency='USD', lines=[{'account_id':11,'debit':'1'},{'account_id':13,'credit':'1'}])
        s.rollback()
        assert s.query(LedgerTransaction).count() == 0
