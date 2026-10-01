package auth

import (
	"context"
	"errors"
	"strings"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/avaargsh/esports-companion/services/api-go/internal/config"
	"github.com/avaargsh/esports-companion/services/api-go/internal/ports"
)

type Service struct {
	repo       Repository
	provider   ports.AuthProvider
	signingKey string
	accessTTL  time.Duration
	refreshTTL time.Duration
	secure     bool
}

func NewService(repo Repository, provider ports.AuthProvider, cfg config.Config) Service {
	return Service{
		repo:       repo,
		provider:   provider,
		signingKey: cfg.SessionSigningKey,
		accessTTL:  time.Duration(cfg.AccessTokenTTLSeconds) * time.Second,
		refreshTTL: time.Duration(cfg.RefreshTokenTTLSeconds) * time.Second,
		secure:     cfg.IsSecureDeployment(),
	}
}

func (s Service) ProviderName() string {
	return s.provider.Name()
}

func (s Service) Login(ctx context.Context, code string) (User, bool, TokenPair, error) {
	identity, err := s.provider.ExchangeCode(ctx, code)
	if err != nil {
		return User{}, false, TokenPair{}, err
	}
	if err := validateSigningKey(s.secure, s.signingKey); err != nil {
		return User{}, false, TokenPair{}, err
	}

	tx, err := s.repo.Begin(ctx)
	if err != nil {
		return User{}, false, TokenPair{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	user, created, err := s.repo.BindUser(ctx, tx, identity)
	if err != nil {
		return User{}, false, TokenPair{}, err
	}
	tokens, err := s.createSession(ctx, tx, user, strings.ToUpper(s.provider.Name()), nil)
	if err != nil {
		return User{}, false, TokenPair{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return User{}, false, TokenPair{}, err
	}
	return user, created, tokens, nil
}

func (s Service) createSession(
	ctx context.Context,
	tx pgx.Tx,
	user User,
	provider string,
	rotatedFromID *string,
) (TokenPair, error) {
	now := time.Now().UTC()
	refreshToken, err := newRefreshToken()
	if err != nil {
		return TokenPair{}, err
	}
	sessionID, err := newUUID()
	if err != nil {
		return TokenPair{}, err
	}
	session := Session{
		ID:        sessionID,
		UserID:    user.ID,
		ExpiresAt: now.Add(s.refreshTTL),
		Provider:  provider,
	}
	if err := s.repo.InsertSession(
		ctx,
		tx,
		session,
		hashRefresh(refreshToken),
		rotatedFromID,
	); err != nil {
		return TokenPair{}, err
	}
	roles, err := s.repo.RolesForUser(ctx, tx, user)
	if err != nil {
		return TokenPair{}, err
	}
	accessToken, err := signAccess(
		user.ID,
		session.ID,
		roles,
		now,
		s.accessTTL,
		s.signingKey,
	)
	if err != nil {
		return TokenPair{}, err
	}
	return TokenPair{
		UserID:           user.ID,
		AccessToken:      accessToken,
		RefreshToken:     refreshToken,
		TokenType:        "Bearer",
		ExpiresIn:        int(s.accessTTL / time.Second),
		RefreshExpiresIn: int(s.refreshTTL / time.Second),
		Roles:            roles,
	}, nil
}

func (s Service) Refresh(ctx context.Context, refreshToken string) (TokenPair, error) {
	if err := validateSigningKey(s.secure, s.signingKey); err != nil {
		return TokenPair{}, err
	}
	now := time.Now().UTC()
	tx, err := s.repo.Begin(ctx)
	if err != nil {
		return TokenPair{}, err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	current, err := s.repo.LockSessionByRefreshHash(ctx, tx, hashRefresh(refreshToken))
	if errors.Is(err, pgx.ErrNoRows) {
		return TokenPair{}, errors.New("REFRESH_TOKEN_INVALID")
	}
	if err != nil {
		return TokenPair{}, err
	}
	if current.RevokedAt != nil {
		if err := s.repo.RevokeDescendants(ctx, tx, current.ID, now); err != nil {
			return TokenPair{}, err
		}
		if err := tx.Commit(ctx); err != nil {
			return TokenPair{}, err
		}
		return TokenPair{}, errors.New("REFRESH_TOKEN_REUSED")
	}
	if !current.ExpiresAt.After(now) {
		return TokenPair{}, errors.New("REFRESH_TOKEN_EXPIRED")
	}

	user, err := userByID(ctx, tx, current.UserID)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && user.Status != "ACTIVE") {
		return TokenPair{}, errors.New("USER_INACTIVE")
	}
	if err != nil {
		return TokenPair{}, err
	}
	if err := s.repo.RevokeSession(ctx, tx, current.ID, now); err != nil {
		return TokenPair{}, err
	}
	next, err := s.createSession(ctx, tx, user, current.Provider, &current.ID)
	if err != nil {
		return TokenPair{}, err
	}
	if err := tx.Commit(ctx); err != nil {
		return TokenPair{}, err
	}
	return next, nil
}

func (s Service) Logout(ctx context.Context, refreshToken string) error {
	now := time.Now().UTC()
	tx, err := s.repo.Begin(ctx)
	if err != nil {
		return err
	}
	defer func() { _ = tx.Rollback(ctx) }()

	session, err := s.repo.LockSessionByRefreshHash(ctx, tx, hashRefresh(refreshToken))
	if errors.Is(err, pgx.ErrNoRows) {
		return tx.Commit(ctx)
	}
	if err != nil {
		return err
	}
	if err := s.repo.RevokeSession(ctx, tx, session.ID, now); err != nil {
		return err
	}
	return tx.Commit(ctx)
}

func (s Service) Authenticate(ctx context.Context, accessToken string) (Principal, error) {
	if err := validateSigningKey(s.secure, s.signingKey); err != nil {
		return Principal{}, err
	}
	now := time.Now().UTC()
	claims, err := decodeAccess(accessToken, s.signingKey, now)
	if err != nil {
		return Principal{}, err
	}
	session, err := s.repo.SessionByID(ctx, claims.SID)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && session.UserID != claims.Sub) {
		return Principal{}, errors.New("ACCESS_SESSION_INVALID")
	}
	if err != nil {
		return Principal{}, err
	}
	if session.RevokedAt != nil {
		return Principal{}, errors.New("ACCESS_SESSION_REVOKED")
	}
	if !session.ExpiresAt.After(now) {
		return Principal{}, errors.New("ACCESS_SESSION_EXPIRED")
	}
	user, err := s.repo.UserByID(ctx, claims.Sub)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && user.Status != "ACTIVE") {
		return Principal{}, errors.New("USER_INACTIVE")
	}
	if err != nil {
		return Principal{}, err
	}
	roles, err := s.repo.RolesForUser(ctx, s.repo.db, user)
	if err != nil {
		return Principal{}, err
	}
	if len(roles) == 0 {
		return Principal{}, errors.New("USER_INACTIVE")
	}
	return Principal{
		User: user, Roles: roles, SessionID: session.ID,
	}, nil
}

func (s Service) LegacyPrincipal(ctx context.Context, userID string) (Principal, error) {
	if !isUUID(userID) {
		return Principal{}, errors.New("LEGACY_USER_INVALID")
	}
	user, err := s.repo.UserByID(ctx, userID)
	if errors.Is(err, pgx.ErrNoRows) || (err == nil && user.Status != "ACTIVE") {
		return Principal{}, errors.New("LEGACY_USER_INVALID")
	}
	if err != nil {
		return Principal{}, err
	}
	roles, err := s.repo.RolesForUser(ctx, s.repo.db, user)
	if err != nil {
		return Principal{}, err
	}
	return Principal{User: user, Roles: roles, Legacy: true}, nil
}
