from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import LedgerAccount, LedgerEntry, LedgerTransaction
from app.ledger_service import post_transaction

@pytest.fixture
def posted():
    engine=create_engine('sqlite:///:memory:')
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([LedgerAccount(id=1,code='immut-a',currency='USD'), LedgerAccount(id=2,code='immut-b',currency='USD')]); db.commit()
        tx_id,_=post_transaction(db,idempotency_key='immutable-test-001',reference='sandbox',currency='USD',lines=[{'account_id':1,'debit':'5.00'},{'account_id':2,'credit':'5.00'}]);db.commit()
        yield db,tx_id
    engine.dispose()

def test_posted_entry_cannot_be_changed(posted):
    db,tx_id=posted
    entry=db.query(LedgerEntry).filter_by(transaction_id=tx_id).first()
    entry.debit=Decimal('999.00')
    with pytest.raises(ValueError,match='immutable'):
        db.flush()
    db.rollback()
    assert db.get(LedgerEntry,entry.id).debit != Decimal('999.00')

def test_posted_entry_cannot_be_deleted(posted):
    db,tx_id=posted
    entry=db.query(LedgerEntry).filter_by(transaction_id=tx_id).first()
    db.delete(entry)
    with pytest.raises(ValueError,match='immutable'):
        db.flush()
    db.rollback()
    assert db.get(LedgerEntry,entry.id) is not None

def test_posted_transaction_cannot_be_changed(posted):
    db,tx_id=posted
    tx=db.get(LedgerTransaction,tx_id)
    tx.reference='altered'
    with pytest.raises(ValueError,match='immutable'):
        db.flush()
    db.rollback()
    assert db.get(LedgerTransaction,tx_id).reference=='sandbox'
