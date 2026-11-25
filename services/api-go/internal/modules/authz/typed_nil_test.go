package authz

import "testing"

func TestNewAuditRepositoryRejectsTypedNilTransaction(t *testing.T) {
	var tx *fakeAuditTx
	if _, err := NewAuditRepository(tx); err == nil {
		t.Fatal("expected typed nil transaction rejection")
	}
}

func TestNewAuditRepositoryAcceptsNonNilTransaction(t *testing.T) {
	tx := &fakeAuditTx{}
	repository, err := NewAuditRepository(tx)
	if err != nil || repository.tx != tx {
		t.Fatalf("expected caller transaction to be retained, got %v", err)
	}
}
