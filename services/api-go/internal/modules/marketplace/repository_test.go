package marketplace

import (
	"reflect"
	"testing"
)

func TestHasRankPreservesGameScopedFiltering(t *testing.T) {
	gameA := "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
	gameB := "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
	skills := []Skill{
		{GameID: gameA, Rank: "Diamond"},
		{GameID: gameB, Rank: "Master"},
	}

	if !hasRank(skills, " diamond ", nil) {
		t.Fatal("rank matching should trim the query and ignore case")
	}
	if !hasRank(skills, "MASTER", &gameB) {
		t.Fatal("expected game-scoped rank match")
	}
	if hasRank(skills, "Master", &gameA) {
		t.Fatal("rank from another game must not satisfy scoped filter")
	}
}

func TestUUIDInClauseUsesBoundParameters(t *testing.T) {
	clause, args := uuidInClause("player_id", []string{"a", "b"}, 3)
	expected := "(player_id = $3::uuid OR player_id = $4::uuid)"
	if clause != expected {
		t.Fatalf("unexpected clause: %s", clause)
	}
	if !reflect.DeepEqual(args, []any{"a", "b"}) {
		t.Fatalf("unexpected args: %#v", args)
	}
}

func TestUUIDInClauseFailsClosedForEmptyInput(t *testing.T) {
	clause, args := uuidInClause("player_id", nil, 1)
	if clause != "FALSE" || len(args) != 0 {
		t.Fatalf("expected empty input to fail closed, got %q %#v", clause, args)
	}
}
