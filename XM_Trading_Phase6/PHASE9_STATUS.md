# Phase 09 — verified scope and outstanding blockers

## Added in this increment
- Database-backed JWT session identifiers, logout and logout-all endpoints; existing tokens without session records are intentionally rejected.
- Alembic revision 0003 for session tracking and preliminary ledger tables.
- Ledger entry one-sided nonnegative check and transaction idempotency unique key.

## NOT COMPLETE / DO NOT DEPLOY FOR FINANCIAL USE
- Ledger posting API, atomic balancing enforcement, approvals, reconciliation and immutable audit storage are NOT implemented. Tables are schema groundwork only.
- OTP remains development-only; no real provider. KYC, AML, market data, licensed broker and real-money settlement remain unconfigured.
- No production infrastructure, credentials, regulatory authorization, signing key or Android release build is provided.
- Android UI is an initial WebView shell; no complete trading app exists.
- Production test matrix, real PostgreSQL migration run, backup restore, device install and security audit remain pending.

## Next steps
1. Configure an isolated PostgreSQL environment and run `alembic upgrade head`; back up the DB first.
2. Run authentication and migration tests against PostgreSQL; add logout regression tests.
3. Implement balanced postings in one serializable transaction with verified external settlement and approval workflow.
4. Integrate contracted OTP/KYC/AML/broker providers; test their sandboxes.
5. Build and test Android APK/AAB in a trusted Android SDK environment with private release signing.

No real-money or trading operations should be enabled.
