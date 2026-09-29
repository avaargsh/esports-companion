.PHONY: up down logs migrate seed test

up:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose run --rm api alembic upgrade head

seed:
	docker compose run --rm api python -m app.seed

test:
	docker compose run --rm api pytest -q
