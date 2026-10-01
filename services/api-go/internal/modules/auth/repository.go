package auth

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgtype"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type queryRower interface {
	QueryRow(context.Context, string, ...any) pgx.Row
}

type Repository struct {
	db *pgxpool.Pool
}

func NewRepository(db *pgxpool.Pool) Repository {
	return Repository{db: db}
}

func (r Repository) Begin(ctx context.Context) (pgx.Tx, error) {
	return r.db.Begin(ctx)
}

func (r Repository) BindUser(ctx context.Context, tx pgx.Tx, identity ports.Identity) (User, bool, error) {
	user, err := findUserByOpenID(ctx, tx, identity.Subject)
	if err == nil {
		user, err = updateIdentity(ctx, tx, user, identity)
		return user, false, err
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return User{}, false, fmt.Errorf("find user by openid: %w", err)
	}

	id, err := newUUID()
	if err != nil {
		return User{}, false, err
	}
	var unionID any
	if identity.UnionID != "" {
		unionID = identity.UnionID
	}
	row := tx.QueryRow(ctx, `
		INSERT INTO users (id, openid, unionid, nickname, role, status)
		VALUES ($1::uuid, $2, $3, $4, 'USER', 'ACTIVE')
		ON CONFLICT (openid) DO NOTHING
		RETURNING id::text, openid, unionid, nickname, role, status
	`, id, identity.Subject, unionID, identity.Nickname)
	user, err = scanUser(row)
	if err == nil {
		return user, true, nil
	}
	if !errors.Is(err, pgx.ErrNoRows) {
		return User{}, false, fmt.Errorf("insert user: %w", err)
	}

	user, err = findUserByOpenID(ctx, tx, identity.Subject)
	if err != nil {
		return User{}, false, fmt.Errorf("recover concurrent user insert: %w", err)
	}
	user, err = updateIdentity(ctx, tx, user, identity)
	return user, false, err
}

func updateIdentity(ctx context.Context, tx pgx.Tx, user User, identity ports.Identity) (User, error) {
	unionID := user.UnionID
	nickname := user.Nickname
	changed := false
	if identity.UnionID != "" && unionID != identity.UnionID {
		unionID = identity.UnionID
		changed = true
	}
	if identity.Nickname != "" && nickname == "" {
		nickname = identity.Nickname
		changed = true
	}
	if !changed {
		return user, nil
	}
	var unionArg any
	if unionID != "" {
		unionArg = unionID
	}
	if _, err := tx.Exec(ctx, `
		UPDATE users
		SET unionid = $2, nickname = $3
		WHERE id = $1::uuid
	`, user.ID, unionArg, nickname); err != nil {
		return User{}, fmt.Errorf("update user identity: %w", err)
	}
	user.UnionID = unionID
	user.Nickname = nickname
	return user, nil
}

func findUserByOpenID(ctx context.Context, q queryRower, openID string) (User, error) {
	return scanUser(q.QueryRow(ctx, `
		SELECT id::text, openid, unionid, nickname, role, status
		FROM users
		WHERE openid = $1
	`, openID))
}

func (r Repository) UserByID(ctx context.Context, id string) (User, error) {
	return userByID(ctx, r.db, id)
}

func userByID(ctx context.Context, q queryRower, id string) (User, error) {
	return scanUser(q.QueryRow(ctx, `
		SELECT id::text, openid, unionid, nickname, role, status
		FROM users
		WHERE id = $1::uuid
	`, id))
}

func scanUser(row pgx.Row) (User, error) {
	var user User
	var openID pgtype.Text
	var unionID pgtype.Text
	if err := row.Scan(
		&user.ID,
		&openID,
		&unionID,
		&user.Nickname,
		&user.Role,
		&user.Status,
	); err != nil {
		return User{}, err
	}
	if openID.Valid {
		user.OpenID = openID.String
	}
	if unionID.Valid {
		user.UnionID = unionID.String
	}
	return user, nil
}

func (r Repository) RolesForUser(ctx context.Context, q queryRower, user User) ([]string, error) {
	if user.Status != "ACTIVE" {
		return []string{}, nil
	}
	var player bool
	if err := q.QueryRow(ctx, `
		SELECT EXISTS(
			SELECT 1
			FROM player_profiles
			WHERE user_id = $1::uuid
			  AND verification_status = 'APPROVED'
		)
	`, user.ID).Scan(&player); err != nil {
		return nil, fmt.Errorf("load user roles: %w", err)
	}
	roles := []string{"USER"}
	if player {
		roles = append(roles, "PLAYER")
	}
	if user.Role == "PLATFORM" || user.Role == "ADMIN" {
		roles = append(roles, "PLATFORM")
	}
	return roles, nil
}

func (r Repository) InsertSession(
	ctx context.Context,
	tx pgx.Tx,
	session Session,
	refreshHash string,
	rotatedFromID *string,
) error {
	var rotated any
	if rotatedFromID != nil {
		rotated = *rotatedFromID
	}
	_, err := tx.Exec(ctx, `
		INSERT INTO auth_sessions (
			id, user_id, refresh_token_hash, expires_at,
			rotated_from_id, provider
		)
		VALUES ($1::uuid, $2::uuid, $3, $4, $5::uuid, $6)
	`, session.ID, session.UserID, refreshHash, session.ExpiresAt, rotated, session.Provider)
	if err != nil {
		return fmt.Errorf("insert auth session: %w", err)
	}
	return nil
}

func (r Repository) LockSessionByRefreshHash(ctx context.Context, tx pgx.Tx, refreshHash string) (Session, error) {
	return scanSession(tx.QueryRow(ctx, `
		SELECT id::text, user_id::text, expires_at, revoked_at, provider
		FROM auth_sessions
		WHERE refresh_token_hash = $1
		FOR UPDATE
	`, refreshHash))
}

func (r Repository) SessionByID(ctx context.Context, id string) (Session, error) {
	return scanSession(r.db.QueryRow(ctx, `
		SELECT id::text, user_id::text, expires_at, revoked_at, provider
		FROM auth_sessions
		WHERE id = $1::uuid
	`, id))
}

func scanSession(row pgx.Row) (Session, error) {
	var session Session
	var revoked pgtype.Timestamptz
	if err := row.Scan(
		&session.ID,
		&session.UserID,
		&session.ExpiresAt,
		&revoked,
		&session.Provider,
	); err != nil {
		return Session{}, err
	}
	if revoked.Valid {
		value := revoked.Time
		session.RevokedAt = &value
	}
	return session, nil
}

func (r Repository) RevokeSession(ctx context.Context, tx pgx.Tx, sessionID string, now time.Time) error {
	_, err := tx.Exec(ctx, `
		UPDATE auth_sessions
		SET revoked_at = COALESCE(revoked_at, $2),
		    last_used_at = $2
		WHERE id = $1::uuid
	`, sessionID, now)
	if err != nil {
		return fmt.Errorf("revoke auth session: %w", err)
	}
	return nil
}

func (r Repository) RevokeDescendants(ctx context.Context, tx pgx.Tx, sessionID string, now time.Time) error {
	_, err := tx.Exec(ctx, `
		WITH RECURSIVE descendants AS (
			SELECT id
			FROM auth_sessions
			WHERE rotated_from_id = $1::uuid
			UNION ALL
			SELECT child.id
			FROM auth_sessions child
			JOIN descendants parent ON child.rotated_from_id = parent.id
		)
		UPDATE auth_sessions
		SET revoked_at = COALESCE(revoked_at, $2),
		    last_used_at = $2
		WHERE id IN (SELECT id FROM descendants)
	`, sessionID, now)
	if err != nil {
		return fmt.Errorf("revoke auth descendants: %w", err)
	}
	return nil
}
