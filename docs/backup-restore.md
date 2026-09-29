# PostgreSQL Backup and Restore Drill

PostgreSQL is the durable source of truth for orders, assignments, payment and
refund records, sessions, ledger entries, disputes and audit events. Redis is
reconstructable and is not part of the durable backup contract.

## Backup format

Backups use PostgreSQL custom format:

```text
pg_dump --format=custom --no-owner --no-privileges
```

Each dump is validated with `pg_restore --list` and accompanied by a SHA-256
checksum.

For a direct/cloud PostgreSQL endpoint:

```bash
DATABASE_URL=postgresql+psycopg://... \
  ./scripts/db_backup.sh backups/esports.dump
```

For the production Compose reference:

```bash
make prod-backup
```

The Compose helper runs `pg_dump` inside the PostgreSQL container, so no local
PostgreSQL client is required.

## Safe restore primitive

The generic restore script deliberately requires an explicit confirmation:

```bash
TARGET_DATABASE_URL=postgresql+psycopg://... \
RESTORE_CONFIRM=RESTORE_TO_TARGET \
  ./scripts/db_restore.sh backups/esports.dump
```

It verifies the checksum when present and uses `pg_restore --exit-on-error`.
The target database must already exist.

Do not point this command at production casually. A real disaster restore
should be performed under an incident/change procedure with the application
stopped or writes fenced.

## Non-destructive production restore drill

The recommended recurring exercise is:

```bash
make prod-backup
make prod-restore-drill BACKUP=backups/esports-YYYYMMDDTHHMMSSZ.dump
```

The drill:

1. verifies the backup checksum;
2. creates a temporary `esports_restore_drill` database;
3. restores the dump with `pg_restore --exit-on-error`;
4. verifies the Alembic version and core seeded/business tables are readable;
5. drops the temporary database on exit.

It does **not** modify the live `esports` database.

## CI acceptance

The `backup-restore` CI job performs a stronger automated drill:

```text
migrate + seed source DB
  -> pg_dump
  -> create fresh DB
  -> pg_restore
  -> schema/data verification
  -> boot FastAPI against restored DB
  -> run real HTTP Golden Slice
```

A green job proves that the artifact is not merely creatable; it is restorable
into a database from which the application can execute its core transaction
path.

## Production policy

Recommended minimum operating policy:

- scheduled encrypted off-host backups;
- retention appropriate to business/legal requirements;
- backup job alerting;
- periodic restore drills against an isolated target;
- record RPO/RTO from observed backup and restore durations;
- keep database credentials and dump encryption keys separate from backup
  storage.

This repository validates logical backup/restore mechanics. Storage encryption,
cross-region retention, PITR/WAL archiving and provider-native snapshots are
deployment responsibilities.
