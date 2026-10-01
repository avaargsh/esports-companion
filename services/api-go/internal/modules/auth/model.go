package auth

import "time"

type User struct {
	ID       string
	OpenID   string
	UnionID  string
	Nickname string
	Role     string
	Status   string
}

type Session struct {
	ID        string
	UserID    string
	ExpiresAt time.Time
	RevokedAt *time.Time
	Provider  string
}

type TokenPair struct {
	UserID           string
	AccessToken      string
	RefreshToken     string
	TokenType        string
	ExpiresIn        int
	RefreshExpiresIn int
	Roles            []string
}

type Principal struct {
	User      User
	Roles     []string
	SessionID string
	Legacy    bool
}

type RequestError struct {
	Status   int
	Code     string
	Location string
	Field    string
	Message  string
}

func (e *RequestError) Error() string {
	if e == nil {
		return ""
	}
	return e.Code
}
