from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import LedgerAccount, LedgerTransaction, LedgerEntry
from app.ledger_service import post_transaction, account_balance
from app.ledger_rules import LedgerValidationError
import pytest

@pytest.fixture
def db():
    engine = create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        s.add_all([LedgerAccount(id=1,code='test-cash',currency='USD'), LedgerAccount(id=2,code='test-clearing',currency='USD')]);s.commit()
        yield s
    engine.dispose()

def test_atomic_idempotency_and_balances(db):
    kw=dict(idempotency_key='test-key-0001',reference='sandbox-only',currency='USD',lines=[{'account_id':1,'debit':'12.50','credit':'0'},{'account_id':2,'debit':'0','credit':'12.50'}])
    tx, created = post_transaction(db, **kw); db.commit()
    assert created
    assert post_transaction(db, **kw)==(tx,False)
    assert account_balance(db,1)==12.5
    assert account_balance(db,2)==-12.5
    assert db.query(LedgerEntry).count()==2
    with pytest.raises(LedgerValidationError):
        post_transaction(db, **{**kw,'reference':'different'})
    assert db.query(LedgerTransaction).count()==1

def test_rejects_unknown_account_and_rolls_back(db):
    with pytest.raises(LedgerValidationError):
        post_transaction(db,idempotency_key='test-key-0002',reference='test',currency='USD',lines=[{'account_id':1,'debit':'1'},{'account_id':99,'credit':'1'}])
    assert db.query(LedgerTransaction).count()==0
