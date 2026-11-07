import os
import sqlite3
import tempfile
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor

from ledger import Ledger, PostingRejected


class LedgerTest(unittest.TestCase):
    def setUp(self):
        dsn = os.getenv("LEDGER_TEST_POSTGRES_DSN")
        if dsn:
            import psycopg
            from psycopg import sql

            schema = "ledger_test_" + uuid.uuid4().hex
            with psycopg.connect(dsn, autocommit=True) as db:
                db.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))

            def cleanup():
                with psycopg.connect(dsn, autocommit=True) as db:
                    db.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))

            self.addCleanup(cleanup)
            def connect():
                db = psycopg.connect(dsn, autocommit=True)
                try:
                    db.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
                    db.autocommit = False
                    return db
                except BaseException:
                    db.close()
                    raise

            self.ledger = Ledger(connect, postgres=True)
        else:
            work = tempfile.TemporaryDirectory()
            self.addCleanup(work.cleanup)
            self.ledger = Ledger(lambda: sqlite3.connect(work.name + "/ledger.sqlite"))
        self.ledger.initialize()
        self.ledger.create_account("client", "USD", "customer")
        self.ledger.create_account("settlement", "USD", "clearing")
        self.ledger.create_account("euro", "EUR", "clearing")

    def test_funding_balances_and_retry(self):
        self.assertTrue(self.ledger.post("fund", "USD", {"client": 100, "settlement": -100}))
        self.assertFalse(self.ledger.post("fund", "USD", {"settlement": -100, "client": 100}))
        with self.assertRaises(PostingRejected):
            self.ledger.post("fund", "USD", {"client": 120, "settlement": -120})
        self.assertEqual(self.ledger.balance("client"), 100)
        self.assertEqual(self.ledger.balance("settlement"), -100)

    def test_invalid_operations_leave_balances_untouched(self):
        for entries in (
            {"client": 100, "settlement": -80},
            {"client": 100, "euro": -100},
            {"client": -100, "settlement": 100},
            {"client": 1.5, "settlement": -1.5},
            {"client": 100, "unknown": -100},
        ):
            with self.subTest(entries=entries), self.assertRaises(PostingRejected):
                self.ledger.post("attempt", "USD", entries)
        self.assertEqual(self.ledger.balance("client"), 0)
        self.assertTrue(self.ledger.post("attempt", "USD", {"client": 100, "settlement": -100}))

    def test_concurrent_withdrawals_cannot_double_spend(self):
        self.ledger.post("fund", "USD", {"client": 100, "settlement": -100})

        def withdraw(n):
            try:
                return self.ledger.post(f"withdraw-{n}", "USD", {"client": -80, "settlement": 80})
            except PostingRejected:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(withdraw, range(2))), 1)
        self.assertEqual(self.ledger.balance("client"), 20)
        self.assertEqual(self.ledger.balance("settlement"), -20)

    def test_database_excludes_drafts_and_rejects_invalid_or_mutated_postings(self):
        from contextlib import closing

        if self.ledger.postgres:
            from psycopg import IntegrityError
        else:
            from sqlite3 import IntegrityError

        def write(sql):
            with closing(self.ledger.connect()) as db, db:
                db.execute(sql)

        write("INSERT INTO ledger_journals VALUES ('draft', 'test', 'USD', 'test')")
        write("INSERT INTO ledger_entries VALUES ('draft', 'client', 100)")
        self.assertEqual(self.ledger.balance("client"), 0)
        with self.assertRaises(IntegrityError):
            write("INSERT INTO ledger_posted VALUES ('draft')")
        self.assertEqual(self.ledger.balance("client"), 0)

        self.ledger.post("posted", "USD", {"client": 100, "settlement": -100})
        for sql in (
            "UPDATE ledger_entries SET amount=500 WHERE journal_id='posted'",
            "DELETE FROM ledger_posted WHERE journal_id='posted'",
            "INSERT INTO ledger_entries VALUES ('posted', 'euro', 5)",
            "UPDATE ledger_accounts SET currency='EUR' WHERE id='client'",
        ):
            with self.subTest(sql=sql), self.assertRaises(IntegrityError):
                write(sql)
        self.assertEqual(self.ledger.balance("client"), 100)
