package authz

import (
	"context"
	"os"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"
)

func TestAuditRepositorySharesCallerTransaction(t *testing.T) {
	dsn := os.Getenv("TEST_DATABASE_URL")
	if dsn == "" {
		t.Skip("TEST_DATABASE_URL is not configured")
	}

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Second)
	defer cancel()

	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		t.Fatalf("connect to PostgreSQL: %v", err)
	}
	defer func() {
		if err := conn.Close(ctx); err != nil {
			t.Errorf("close PostgreSQL connection: %v", err)
		}
	}()

	_, err = conn.Exec(ctx, `
		CREATE TEMP TABLE outbox_events (
			id UUID PRIMARY KEY,
			aggregate_type VARCHAR(64) NOT NULL,
			aggregate_id VARCHAR(128) NOT NULL,
			event_type VARCHAR(80) NOT NULL,
			payload_json JSON NOT NULL,
			status VARCHAR(32) NOT NULL
		)
	`)
	if err != nil {
		t.Fatalf("create outbox test table: %v", err)
	}
	_, err = conn.Exec(ctx, `
		CREATE TEMP TABLE business_mutations (
			id INTEGER PRIMARY KEY,
			status TEXT NOT NULL
		)
	`)
	if err != nil {
		t.Fatalf("create business mutation test table: %v", err)
	}

	rollbackTx, err := conn.Begin(ctx)
	if err != nil {
		t.Fatalf("begin rollback transaction: %v", err)
	}
	rollbackRepository, err := NewAuditRepository(rollbackTx)
	if err != nil {
		t.Fatalf("create rollback audit repository: %v", err)
	}
	if err := rollbackRepository.RecordDecision(ctx, referenceDecision(), nil); err != nil {
		t.Fatalf("record audit in rollback transaction: %v", err)
	}
	if _, err := rollbackTx.Exec(ctx, `
		INSERT INTO business_mutations (id, status) VALUES (1, 'APPLIED')
	`); err != nil {
		t.Fatalf("write business mutation in rollback transaction: %v", err)
	}
	if err := rollbackTx.Rollback(ctx); err != nil {
		t.Fatalf("rollback caller transaction: %v", err)
	}

	var auditCount, mutationCount int64
	if err := conn.QueryRow(ctx, "SELECT count(*) FROM outbox_events").Scan(&auditCount); err != nil {
		t.Fatalf("count audit rows after rollback: %v", err)
	}
	if err := conn.QueryRow(ctx, "SELECT count(*) FROM business_mutations").Scan(&mutationCount); err != nil {
		t.Fatalf("count business rows after rollback: %v", err)
	}
	if auditCount != 0 || mutationCount != 0 {
		t.Fatalf("rollback must remove both writes: audit=%d business=%d", auditCount, mutationCount)
	}

	commitTx, err := conn.Begin(ctx)
	if err != nil {
		t.Fatalf("begin commit transaction: %v", err)
	}
	commitRepository, err := NewAuditRepository(commitTx)
	if err != nil {
		t.Fatalf("create commit audit repository: %v", err)
	}
	if err := commitRepository.RecordDecision(ctx, referenceDecision(), nil); err != nil {
		_ = commitTx.Rollback(ctx)
		t.Fatalf("record audit in commit transaction: %v", err)
	}
	if _, err := commitTx.Exec(ctx, `
		INSERT INTO business_mutations (id, status) VALUES (2, 'APPLIED')
	`); err != nil {
		_ = commitTx.Rollback(ctx)
		t.Fatalf("write business mutation in commit transaction: %v", err)
	}
	if err := commitTx.Commit(ctx); err != nil {
		t.Fatalf("commit caller transaction: %v", err)
	}

	if err := conn.QueryRow(ctx, "SELECT count(*) FROM outbox_events").Scan(&auditCount); err != nil {
		t.Fatalf("count audit rows after commit: %v", err)
	}
	if err := conn.QueryRow(ctx, "SELECT count(*) FROM business_mutations").Scan(&mutationCount); err != nil {
		t.Fatalf("count business rows after commit: %v", err)
	}
	if auditCount != 1 || mutationCount != 1 {
		t.Fatalf("commit must persist both writes exactly once: audit=%d business=%d", auditCount, mutationCount)
	}
}
