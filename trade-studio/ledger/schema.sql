CREATE TABLE IF NOT EXISTS ledger_lock (
    id INTEGER PRIMARY KEY CHECK (id = 1)
);
INSERT INTO ledger_lock (id) VALUES (1) ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS ledger_accounts (
    id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('customer', 'clearing'))
);
CREATE TABLE IF NOT EXISTS ledger_journals (
    id TEXT PRIMARY KEY,
    fingerprint TEXT NOT NULL,
    currency TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ledger_entries (
    journal_id TEXT NOT NULL REFERENCES ledger_journals (id),
    account_id TEXT NOT NULL REFERENCES ledger_accounts (id),
    amount BIGINT NOT NULL CHECK (amount <> 0),
    PRIMARY KEY (journal_id, account_id)
);
CREATE INDEX IF NOT EXISTS ledger_entries_account ON ledger_entries (account_id);

CREATE TABLE IF NOT EXISTS ledger_posted (
    journal_id TEXT PRIMARY KEY REFERENCES ledger_journals (id)
);
