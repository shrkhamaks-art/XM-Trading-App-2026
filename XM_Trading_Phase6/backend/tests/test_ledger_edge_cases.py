"""Additional sandbox ledger regression checks (SQLite, not PostgreSQL)."""
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import LedgerAccount, LedgerTransaction
from app.ledger_service import post_transaction, account_balance
from app.ledger_rules import LedgerValidationError

@pytest.fixture
def dbengine(tmp_path):
    e=create_engine(f"sqlite:///{tmp_path/'edge.db'}")
    Base.metadata.create_all(e)
    with Session(e) as s:
        s.add_all([LedgerAccount(id=101,code='cash',currency='USD'),LedgerAccount(id=102,code='offset',currency='USD')]);s.commit()
    yield e
    e.dispose()

def request(amount='12.50',key='edge-test-key-0001'):
    return dict(idempotency_key=key,reference='edge',currency='USD',lines=[{'account_id':101,'debit':amount},{'account_id':102,'credit':amount}])

def test_equivalent_decimal_replay(dbengine):
    with Session(dbengine) as s:
        tx,created=post_transaction(s,**request());s.commit()
    with Session(dbengine) as s:
        assert post_transaction(s,**request('12.5000'))==(tx,False)
        assert account_balance(s,101)==Decimal('12.5000')

def test_reject_invalid_account_without_persistence(dbengine):
    with Session(dbengine) as s:
        bad=request();bad['lines'][1]['account_id']=999
        with pytest.raises(LedgerValidationError):post_transaction(s,**bad)
        s.rollback()
    with Session(dbengine) as s:assert s.query(LedgerTransaction).count()==0

def test_duplicate_key_different_reference_rejected(dbengine):
    with Session(dbengine) as s:post_transaction(s,**request());s.commit()
    with Session(dbengine) as s:
        bad=request();bad['reference']='different'
        with pytest.raises(LedgerValidationError):post_transaction(s,**bad)
        s.rollback()
