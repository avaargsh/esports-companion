package marketplace

import (
	"context"
	"errors"
	"fmt"
	"strings"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"
)

var ErrPlayerNotFound = errors.New("PLAYER_NOT_FOUND")

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) ListPlayers(ctx context.Context, q ListQuery) ([]Player, error) {
	candidates, err := r.listCandidates(ctx, q.Limit)
	if err != nil {
		return nil, err
	}
	if len(candidates) == 0 {
		return []Player{}, nil
	}

	ids := make([]string, 0, len(candidates))
	for _, item := range candidates {
		ids = append(ids, item.ID)
	}

	ratings, err := r.ratingsFor(ctx, ids)
	if err != nil {
		return nil, err
	}
	offerings, err := r.offeringsFor(ctx, ids)
	if err != nil {
		return nil, err
	}
	skills, err := r.skillsFor(ctx, ids)
	if err != nil {
		return nil, err
	}

	result := make([]Player, 0, len(candidates))
	for _, player := range candidates {
		if rating, ok := ratings[player.ID]; ok {
			player.Rating = rating.rating
			player.ReviewCount = rating.count
		}
		player.Offerings = offerings[player.ID]
		if player.Offerings == nil {
			player.Offerings = []Offering{}
		}
		player.Skills = skills[player.ID]
		if player.Skills == nil {
			player.Skills = []Skill{}
		}
		player.Reviews = []Review{}

		if q.GameID != nil && !hasGameOffering(player.Offerings, *q.GameID) {
			continue
		}
		if q.Rank != nil && !hasRank(player.Skills, *q.Rank, q.GameID) {
			continue
		}
		if len(player.Offerings) == 0 {
			continue
		}
		result = append(result, player)
	}
	return result, nil
}

func (r Repository) GetPlayer(ctx context.Context, playerID string) (Player, error) {
	var player Player
	var avatar pgtype.Text
	var gender pgtype.Text

	err := r.db.QueryRow(ctx, `
		SELECT
			p.id::text,
			p.display_name,
			u.avatar_url,
			p.bio,
			p.gender,
			p.service_status,
			p.order_count
		FROM player_profiles p
		LEFT JOIN users u ON u.id = p.user_id
		WHERE p.id = $1::uuid
		  AND p.verification_status = 'APPROVED'
	`, playerID).Scan(
		&player.ID,
		&player.DisplayName,
		&avatar,
		&player.Bio,
		&gender,
		&player.ServiceStatus,
		&player.OrderCount,
	)
	if errors.Is(err, pgx.ErrNoRows) {
		return Player{}, ErrPlayerNotFound
	}
	if err != nil {
		return Player{}, fmt.Errorf("get player: %w", err)
	}
	if avatar.Valid {
		value := avatar.String
		player.AvatarURL = &value
	}
	if gender.Valid {
		value := gender.String
		player.Gender = &value
	}

	ratings, err := r.ratingsFor(ctx, []string{player.ID})
	if err != nil {
		return Player{}, err
	}
	if rating, ok := ratings[player.ID]; ok {
		player.Rating = rating.rating
		player.ReviewCount = rating.count
	}
	offerings, err := r.offeringsFor(ctx, []string{player.ID})
	if err != nil {
		return Player{}, err
	}
	skills, err := r.skillsFor(ctx, []string{player.ID})
	if err != nil {
		return Player{}, err
	}
	reviews, err := r.reviewsFor(ctx, player.ID)
	if err != nil {
		return Player{}, err
	}

	player.Offerings = offerings[player.ID]
	if player.Offerings == nil {
		player.Offerings = []Offering{}
	}
	player.Skills = skills[player.ID]
	if player.Skills == nil {
		player.Skills = []Skill{}
	}
	player.Reviews = reviews
	return player, nil
}

func (r Repository) listCandidates(ctx context.Context, limit int) ([]Player, error) {
	rows, err := r.db.Query(ctx, `
		SELECT
			p.id::text,
			p.display_name,
			u.avatar_url,
			p.bio,
			p.gender,
			p.service_status,
			p.order_count
		FROM player_profiles p
		LEFT JOIN users u ON u.id = p.user_id
		WHERE p.verification_status = 'APPROVED'
		  AND p.service_status = 'AVAILABLE'
		ORDER BY p.rating DESC, p.created_at
		LIMIT $1
	`, limit)
	if err != nil {
		return nil, fmt.Errorf("list player candidates: %w", err)
	}
	defer rows.Close()

	result := make([]Player, 0, limit)
	for rows.Next() {
		var item Player
		var avatar pgtype.Text
		var gender pgtype.Text
		if err := rows.Scan(
			&item.ID,
			&item.DisplayName,
			&avatar,
			&item.Bio,
			&gender,
			&item.ServiceStatus,
			&item.OrderCount,
		); err != nil {
			return nil, fmt.Errorf("scan player candidate: %w", err)
		}
		if avatar.Valid {
			value := avatar.String
			item.AvatarURL = &value
		}
		if gender.Valid {
			value := gender.String
			item.Gender = &value
		}
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate player candidates: %w", err)
	}
	return result, nil
}

type ratingSummary struct {
	rating float64
	count  int
}

func (r Repository) ratingsFor(ctx context.Context, ids []string) (map[string]ratingSummary, error) {
	clause, args := uuidInClause("player_id", ids, 1)
	rows, err := r.db.Query(ctx, `
		SELECT player_id::text, COALESCE(AVG(rating), 0)::float8, COUNT(id)::int
		FROM reviews
		WHERE `+clause+`
		GROUP BY player_id
	`, args...)
	if err != nil {
		return nil, fmt.Errorf("load ratings: %w", err)
	}
	defer rows.Close()

	result := make(map[string]ratingSummary, len(ids))
	for rows.Next() {
		var playerID string
		var summary ratingSummary
		if err := rows.Scan(&playerID, &summary.rating, &summary.count); err != nil {
			return nil, fmt.Errorf("scan rating: %w", err)
		}
		result[playerID] = summary
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate ratings: %w", err)
	}
	return result, nil
}

func (r Repository) offeringsFor(ctx context.Context, ids []string) (map[string][]Offering, error) {
	clause, args := uuidInClause("o.player_id", ids, 1)
	rows, err := r.db.Query(ctx, `
		SELECT
			o.player_id::text,
			o.id::text,
			s.id::text,
			g.id::text,
			g.name,
			s.name,
			s.service_type,
			s.duration_minutes,
			COALESCE(o.price_override, s.price),
			o.description
		FROM provider_offerings o
		JOIN service_skus s ON s.id = o.sku_id
		JOIN games g ON g.id = s.game_id
		WHERE `+clause+`
		  AND o.status = 'ACTIVE'
		  AND s.status = 'ACTIVE'
		  AND g.status = 'ACTIVE'
		ORDER BY o.player_id, g.sort_order, s.price
	`, args...)
	if err != nil {
		return nil, fmt.Errorf("load offerings: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]Offering, len(ids))
	for rows.Next() {
		var playerID string
		var item Offering
		if err := rows.Scan(
			&playerID,
			&item.ID,
			&item.SKUID,
			&item.GameID,
			&item.GameName,
			&item.SKUName,
			&item.ServiceType,
			&item.DurationMinutes,
			&item.Price,
			&item.Description,
		); err != nil {
			return nil, fmt.Errorf("scan offering: %w", err)
		}
		result[playerID] = append(result[playerID], item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate offerings: %w", err)
	}
	return result, nil
}

func (r Repository) skillsFor(ctx context.Context, ids []string) (map[string][]Skill, error) {
	clause, args := uuidInClause("s.player_id", ids, 1)
	rows, err := r.db.Query(ctx, `
		SELECT
			s.player_id::text,
			s.id::text,
			g.id::text,
			g.name,
			s.rank,
			s.description
		FROM player_skills s
		JOIN games g ON g.id = s.game_id
		WHERE `+clause+`
		  AND s.status = 'ACTIVE'
		  AND s.verification_status = 'APPROVED'
		  AND g.status = 'ACTIVE'
		  AND s.rank IS NOT NULL
		  AND s.rank <> ''
		ORDER BY s.player_id, g.sort_order, s.updated_at DESC
	`, args...)
	if err != nil {
		return nil, fmt.Errorf("load skills: %w", err)
	}
	defer rows.Close()

	result := make(map[string][]Skill, len(ids))
	for rows.Next() {
		var playerID string
		var item Skill
		if err := rows.Scan(
			&playerID,
			&item.ID,
			&item.GameID,
			&item.GameName,
			&item.Rank,
			&item.Description,
		); err != nil {
			return nil, fmt.Errorf("scan skill: %w", err)
		}
		result[playerID] = append(result[playerID], item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate skills: %w", err)
	}
	return result, nil
}

func (r Repository) reviewsFor(ctx context.Context, playerID string) ([]Review, error) {
	rows, err := r.db.Query(ctx, `
		SELECT id::text, rating, content
		FROM reviews
		WHERE player_id = $1::uuid
		ORDER BY created_at DESC
		LIMIT 20
	`, playerID)
	if err != nil {
		return nil, fmt.Errorf("load reviews: %w", err)
	}
	defer rows.Close()

	result := make([]Review, 0)
	for rows.Next() {
		var item Review
		if err := rows.Scan(&item.ID, &item.Rating, &item.Content); err != nil {
			return nil, fmt.Errorf("scan review: %w", err)
		}
		result = append(result, item)
	}
	if err := rows.Err(); err != nil {
		return nil, fmt.Errorf("iterate reviews: %w", err)
	}
	return result, nil
}

func uuidInClause(column string, ids []string, start int) (string, []any) {
	parts := make([]string, 0, len(ids))
	args := make([]any, 0, len(ids))
	for i, id := range ids {
		parts = append(parts, fmt.Sprintf("%s = $%d::uuid", column, start+i))
		args = append(args, id)
	}
	if len(parts) == 0 {
		return "FALSE", args
	}
	return "(" + strings.Join(parts, " OR ") + ")", args
}

func hasGameOffering(items []Offering, gameID string) bool {
	for _, item := range items {
		if item.GameID == gameID {
			return true
		}
	}
	return false
}

func hasRank(items []Skill, rank string, gameID *string) bool {
	normalized := strings.TrimSpace(rank)
	for _, item := range items {
		if !strings.EqualFold(item.Rank, normalized) {
			continue
		}
		if gameID == nil || item.GameID == *gameID {
			return true
		}
	}
	return false
}
