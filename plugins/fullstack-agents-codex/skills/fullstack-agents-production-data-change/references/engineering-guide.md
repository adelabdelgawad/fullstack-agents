# Production data change

The agent reads production only through a read-only session (Postgres:
`PGOPTIONS='-c default_transaction_read_only=on'`). It writes the change as a script; whoever the
project names (usually the user) runs it against production. The project's `CLAUDE.md` names the
database, its access command and who may write; a missing binding means the user runs it.

## Script shape

- One file, one transaction, `\set ON_ERROR_STOP on`, a `BEGIN;` and **no** `COMMIT` or `ROLLBACK`:
  the run appends one, so the dry run and the real run execute the identical text.
- Guard every step with the expected row counts, failing the transaction when they differ
  (`DO $$ ... IF n <> expected THEN RAISE EXCEPTION ... END $$;`). Expected counts come from
  read-only queries the agent ran, written into the script with their query and time.
- Print the before/after counts the user will compare (`SELECT ... AS before_x`).
- Natural keys, never generated ids copied from another environment. Batch big updates.
- A delete keeps what it removes: `CREATE TABLE ... AS SELECT` into a dated backup table first, or a
  written forward-fix that restores it.

## Order

1. **Read**: count the affected rows read-only; name what one row means and its null cases.
2. **Prove**: run the script on a throwaway copy (a disposable database restored from a dump of the
   affected tables, or the project's test database) with `COMMIT`, then check the result there.
3. **Dry run** (the user, on production): `sed '$a ROLLBACK;' <script> | <psql access command>`;
   read the printed counts together.
4. **Real run** (the user): `sed '$a COMMIT;' <script> | <psql access command>`.
5. **Verify** read-only: the counts, a sample of changed rows, and the application view that shows them.

Give the user the absolute path of the script and both commands. Secrets come from the host's
environment or files, never from the chat.
