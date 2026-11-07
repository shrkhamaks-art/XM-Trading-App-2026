CREATE TRIGGER IF NOT EXISTS validate_posting
BEFORE INSERT ON ledger_posted
BEGIN
    SELECT CASE WHEN NOT EXISTS (
        SELECT 1 FROM ledger_journals WHERE id = NEW.journal_id
    ) OR (
        SELECT COUNT(*) FROM ledger_entries WHERE journal_id = NEW.journal_id
    ) < 2 OR (
        SELECT SUM(amount) FROM ledger_entries WHERE journal_id = NEW.journal_id
    ) <> 0 OR EXISTS (
        SELECT 1 FROM ledger_entries e
        JOIN ledger_journals j ON j.id = e.journal_id
        LEFT JOIN ledger_accounts a ON a.id = e.account_id
        WHERE e.journal_id = NEW.journal_id
          AND (a.id IS NULL OR a.currency <> j.currency OR typeof(e.amount) <> 'integer')
    ) THEN RAISE(ABORT, 'Invalid journal posting') END;
END;

CREATE TRIGGER IF NOT EXISTS guard_entry_insert
BEFORE INSERT ON ledger_entries
WHEN EXISTS (SELECT 1 FROM ledger_posted WHERE journal_id = NEW.journal_id)
BEGIN
    SELECT RAISE(ABORT, 'Journal already posted');
END;

CREATE TRIGGER IF NOT EXISTS ledger_entries_update_guard
BEFORE UPDATE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_entries_delete_guard
BEFORE DELETE ON ledger_entries
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_posted_update_guard
BEFORE UPDATE ON ledger_posted
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_posted_delete_guard
BEFORE DELETE ON ledger_posted
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_journals_update_guard
BEFORE UPDATE ON ledger_journals
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_journals_delete_guard
BEFORE DELETE ON ledger_journals
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_accounts_update_guard
BEFORE UPDATE ON ledger_accounts
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;

CREATE TRIGGER IF NOT EXISTS ledger_accounts_delete_guard
BEFORE DELETE ON ledger_accounts
BEGIN
    SELECT RAISE(ABORT, 'Ledger records are append-only');
END;
