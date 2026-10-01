package redisx

import (
	"fmt"

	"github.com/redis/go-redis/v9"
)

func Open(rawURL string, poolSize int) (*redis.Client, error) {
	options, err := redis.ParseURL(rawURL)
	if err != nil {
		return nil, fmt.Errorf("parse redis url: %w", err)
	}
	options.PoolSize = poolSize
	options.MinIdleConns = max(2, poolSize/8)
	return redis.NewClient(options), nil
}
