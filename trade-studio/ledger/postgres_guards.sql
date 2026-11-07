CREATE OR REPLACE FUNCTION ledger_guard_posting() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM ledger_journals WHERE id = NEW.journal_id FOR UPDATE;
    IF NOT FOUND OR (
        SELECT COUNT(*) FROM ledger_entries WHERE journal_id = NEW.journal_id
    ) < 2 OR (
        SELECT SUM(amount) FROM ledger_entries WHERE journal_id = NEW.journal_id
    ) <> 0 OR EXISTS (
        SELECT 1 FROM ledger_entries e
        JOIN ledger_journals j ON j.id = e.journal_id
        JOIN ledger_accounts a ON a.id = e.account_id
        WHERE e.journal_id = NEW.journal_id AND a.currency <> j.currency
    ) THEN
        RAISE EXCEPTION 'Invalid journal posting' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ledger_guard_entry() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    PERFORM 1 FROM ledger_journals WHERE id = NEW.journal_id FOR UPDATE;
    IF EXISTS (SELECT 1 FROM ledger_posted WHERE journal_id = NEW.journal_id) THEN
        RAISE EXCEPTION 'Journal already posted' USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION ledger_reject_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Ledger records are append-only' USING ERRCODE = '23514';
END;
$$;

CREATE OR REPLACE TRIGGER validate_posting BEFORE INSERT ON ledger_posted
FOR EACH ROW EXECUTE FUNCTION ledger_guard_posting();
CREATE OR REPLACE TRIGGER guard_entry_insert BEFORE INSERT ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION ledger_guard_entry();

CREATE OR REPLACE TRIGGER ledger_entries_mutation_guard
BEFORE UPDATE OR DELETE ON ledger_entries
FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation();

CREATE OR REPLACE TRIGGER ledger_posted_mutation_guard
BEFORE UPDATE OR DELETE ON ledger_posted
FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation();

CREATE OR REPLACE TRIGGER ledger_journals_mutation_guard
BEFORE UPDATE OR DELETE ON ledger_journals
FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation();

CREATE OR REPLACE TRIGGER ledger_accounts_mutation_guard
BEFORE UPDATE OR DELETE ON ledger_accounts
FOR EACH ROW EXECUTE FUNCTION ledger_reject_mutation();
