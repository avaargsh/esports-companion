package orders

import (
	"context"
	"errors"
	"testing"
)

func TestServiceCreateRequiresExactlyOneSource(t *testing.T) {
	service := Service{}

	_, err := service.Create(context.Background(), "user-1", CreateInput{
		Quantity: 1,
	})
	if !errors.Is(err, ErrExactlyOneSKUOrOffering) {
		t.Fatalf("expected exact-one error for empty source, got %v", err)
	}

	skuID := "sku-1"
	offeringID := "offering-1"
	_, err = service.Create(context.Background(), "user-1", CreateInput{
		SKUID:      &skuID,
		OfferingID: &offeringID,
		Quantity:   1,
	})
	if !errors.Is(err, ErrExactlyOneSKUOrOffering) {
		t.Fatalf("expected exact-one error for dual source, got %v", err)
	}
}
