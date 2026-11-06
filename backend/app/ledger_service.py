"""Atomic, idempotent INTERNAL ledger posting. No external money movement."""
from decimal import Decimal
from hashlib import sha256
import json
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from .models import LedgerAccount, LedgerTransaction, LedgerEntry
from . import ledger_guards  # register ORM immutability hooks
from .ledger_rules import validate_posting, LedgerValidationError


def post_transaction(session, *, idempotency_key, reference, currency, lines):
    if not isinstance(idempotency_key, str) or not (8 <= len(idempotency_key) <= 128):
        raise LedgerValidationError('Idempotency key must be 8-128 characters')
    if not isinstance(reference, str) or not (1 <= len(reference) <= 255):
        raise LedgerValidationError('Reference required')
    validate_posting(lines, currency)
    canonical = sorted([{'account_id': int(l['account_id']), 'debit': format(Decimal(str(l.get('debit', 0))).quantize(Decimal('0.0001')), 'f'), 'credit': format(Decimal(str(l.get('credit', 0))).quantize(Decimal('0.0001')), 'f')} for l in lines], key=lambda x:(x['account_id'], x['debit'], x['credit']))
    fingerprint = sha256(json.dumps([reference,currency,canonical], separators=(',', ':')).encode()).hexdigest()
    # Caller owns transaction boundary; savepoint makes failed posting non-destructive.
    try:
        with session.begin_nested():
            existing = session.scalar(select(LedgerTransaction).where(LedgerTransaction.idempotency_key == idempotency_key))
            if existing:
                if existing.reference != reference or existing.currency != currency or existing.request_hash != fingerprint:
                    raise LedgerValidationError('Idempotency key reused with different payload')
                return existing.id, False
            ids = {l['account_id'] for l in canonical}
            accounts = session.scalars(select(LedgerAccount).where(LedgerAccount.id.in_(ids))).all()
            if len(accounts) != len(ids) or any(a.currency != currency for a in accounts):
                raise LedgerValidationError('Unknown account or currency mismatch')
            tx = LedgerTransaction(idempotency_key=idempotency_key, reference=reference, currency=currency, request_hash=fingerprint)
            session.add(tx)
            session.flush()
            session.add_all([LedgerEntry(transaction_id=tx.id, account_id=l['account_id'], debit=Decimal(l['debit']), credit=Decimal(l['credit'])) for l in canonical])
            session.flush()
            return tx.id, True
    except IntegrityError:
        # A concurrent writer may have won the unique-key race. Caller should retry with a fresh session.
        raise LedgerValidationError('Concurrent duplicate: retry lookup in a new transaction')


def account_balance(session, account_id):
    debit, credit = session.execute(select(func.coalesce(func.sum(LedgerEntry.debit), 0), func.coalesce(func.sum(LedgerEntry.credit), 0)).where(LedgerEntry.account_id == account_id)).one()
    return Decimal(debit) - Decimal(credit)
