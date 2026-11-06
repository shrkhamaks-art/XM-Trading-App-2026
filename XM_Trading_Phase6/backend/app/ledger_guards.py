"""Application-level guard against mutation of posted ledger rows.
Database permissions/triggers are still required for production enforcement.
"""
from sqlalchemy import event
from .models import LedgerEntry, LedgerTransaction


def _deny_mutation(mapper, connection, target):
    raise ValueError('Posted ledger records are immutable; use a reversing entry')


for model in (LedgerEntry, LedgerTransaction):
    event.listen(model, 'before_update', _deny_mutation)
    event.listen(model, 'before_delete', _deny_mutation)
