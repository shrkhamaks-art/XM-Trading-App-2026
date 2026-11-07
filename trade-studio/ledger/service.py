"""Internal sandbox ledger. Amounts are signed integer minor units."""

import hashlib
import json
import re
import sqlite3
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path


class PostingRejected(ValueError):
    pass


class Ledger:
    def __init__(self, connect, *, postgres=False):
        self.connect = connect
        self.postgres = postgres

    def initialize(self):
        directory = Path(__file__).parent
        backend = "postgres" if self.postgres else "sqlite"
        with closing(self.connect()) as db:
            if not self.postgres:
                db.execute("PRAGMA foreign_keys = ON")
            with db.transaction() if self.postgres else db:
                if not self.postgres:
                    db.execute("BEGIN IMMEDIATE")
                exists = (
                    db.execute("SELECT to_regclass('ledger_posted')").fetchone()[0]
                    if self.postgres else
                    db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='ledger_posted'").fetchone()
                )
                for filename in ("schema.sql", f"{backend}_guards.sql"):
                    script = (directory / filename).read_text()
                    if self.postgres:
                        db.execute(script)
                    else:
                        statement = ""
                        for line in script.splitlines(keepends=True):
                            statement += line
                            if sqlite3.complete_statement(statement):
                                db.execute(statement)
                                statement = ""
                # On upgrade, accept old journals only if they pass the new guards.
                if not exists:
                    db.execute("INSERT INTO ledger_posted SELECT id FROM ledger_journals")

    @contextmanager
    def _transaction(self):
        with closing(self.connect()) as db:
            if self.postgres:
                with db.transaction():
                    db.execute("SELECT id FROM ledger_lock WHERE id = 1 FOR UPDATE")
                    yield db
            else:
                db.execute("PRAGMA foreign_keys = ON")
                with db:
                    db.execute("BEGIN IMMEDIATE")
                    yield db

    def _query(self, db, sql, values):
        return db.execute(sql.replace("?", "%s") if self.postgres else sql, values)

    def create_account(self, account_id, currency, kind):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", account_id):
            raise PostingRejected("Invalid account identifier")
        if not re.fullmatch(r"[A-Z]{3,8}", currency) or kind not in {"customer", "clearing"}:
            raise PostingRejected("Invalid account configuration")
        with self._transaction() as db:
            self._query(db, "INSERT INTO ledger_accounts VALUES (?, ?, ?)",
                        (account_id, currency, kind))

    def _balance(self, db, account_id):
        result = self._query(db, "SELECT COALESCE(SUM(e.amount), 0) FROM ledger_entries e JOIN ledger_posted p ON p.journal_id = e.journal_id WHERE e.account_id = ?",
                             (account_id,)).fetchone()
        return int(result[0])

    def balance(self, account_id):
        with closing(self.connect()) as db:
            if not self._query(db, "SELECT 1 FROM ledger_accounts WHERE id = ?", (account_id,)).fetchone():
                raise PostingRejected("Unknown account")
            return self._balance(db, account_id)

    def post(self, journal_id, currency, entries):
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", journal_id):
            raise PostingRejected("Invalid journal identifier")
        entries = sorted(entries.items())
        if not 2 <= len(entries) <= 32 or any(
            type(amount) is not int or not 0 < abs(amount) <= 10**15 for _, amount in entries
        ) or sum(amount for _, amount in entries) != 0:
            raise PostingRejected("Entries must be nonzero integer minor units and balance to zero")
        fingerprint = hashlib.sha256(json.dumps([currency, entries]).encode()).hexdigest()

        with self._transaction() as db:
            existing = self._query(db, "SELECT j.fingerprint, p.journal_id FROM ledger_journals j LEFT JOIN ledger_posted p ON p.journal_id = j.id WHERE j.id = ?",
                                   (journal_id,)).fetchone()
            if existing:
                if existing[1] is None:
                    raise PostingRejected("Journal ID belongs to an unposted journal")
                if existing[0] != fingerprint:
                    raise PostingRejected("Journal ID was already used for different entries")
                return False
            for account_id, amount in entries:
                account = self._query(db, "SELECT currency, kind FROM ledger_accounts WHERE id = ?",
                                      (account_id,)).fetchone()
                if not account or account[0] != currency:
                    raise PostingRejected("Every account must exist and match the journal currency")
                new_balance = self._balance(db, account_id) + amount
                if account[1] == "customer" and new_balance < 0:
                    raise PostingRejected("Insufficient balance")
                if abs(new_balance) > 10**18:
                    raise PostingRejected("Balance exceeds supported range")

            created = datetime.now(timezone.utc).isoformat()
            self._query(db, "INSERT INTO ledger_journals VALUES (?, ?, ?, ?)",
                        (journal_id, fingerprint, currency, created))
            for account_id, amount in entries:
                self._query(db, "INSERT INTO ledger_entries VALUES (?, ?, ?)",
                            (journal_id, account_id, amount))
            self._query(db, "INSERT INTO ledger_posted VALUES (?)", (journal_id,))
            return True
