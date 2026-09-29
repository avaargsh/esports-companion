.PHONY: up down logs migrate seed test miniapp-build admin-build prod-build prod-up prod-down prod-logs

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


miniapp-build:
	cd apps/miniapp && npm install --no-audit --no-fund && npm run build:mp-weixin

admin-build:
	cd apps/admin && npm install --no-audit --no-fund && npm run build


prod-build:
	docker compose --env-file .env.production -f deploy/compose/production.yml build api

prod-up:
	docker compose --env-file .env.production -f deploy/compose/production.yml up -d --build

prod-down:
	docker compose --env-file .env.production -f deploy/compose/production.yml down

prod-logs:
	docker compose --env-file .env.production -f deploy/compose/production.yml logs -f api
