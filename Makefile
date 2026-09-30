.PHONY: up down logs migrate seed test go-test go-build go-run go-parity smoke verify miniapp-build miniapp-staging-build admin-build prod-build prod-up prod-down prod-logs prod-backup prod-restore-drill staging-preflight staging-build staging-up staging-down staging-logs staging-check staging-wechat-evidence

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

go-test:
	cd services/api-go && go test -race ./...

go-build:
	cd services/api-go && go build ./cmd/api ./cmd/worker

go-run:
	cd services/api-go && go run ./cmd/api

go-parity:
	python3 scripts/go_read_parity.py
	python3 scripts/go_auth_parity.py
	python3 scripts/go_offering_parity.py
	python3 scripts/go_order_read_parity.py
	python3 scripts/go_order_create_parity.py
	python3 scripts/go_claim_parity.py
	python3 scripts/go_lifecycle_parity.py
	python3 scripts/go_settlement_parity.py
	python3 scripts/go_mock_payment_parity.py
	python3 scripts/go_payment_prepare_parity.py

smoke:
	python3 scripts/smoke_demo.py

verify: test miniapp-build admin-build


miniapp-build:
	cd apps/miniapp && npm install --no-audit --no-fund && npm run build:mp-weixin

miniapp-staging-build:
	@test -f apps/miniapp/.env.staging || (echo "copy apps/miniapp/.env.staging.example to apps/miniapp/.env.staging and set the real staging API origin" && exit 64)
	cd apps/miniapp && npm install --no-audit --no-fund && npm run build:mp-weixin:staging

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


prod-backup:
	./scripts/prod_backup.sh

prod-restore-drill:
	@test -n "$(BACKUP)" || (echo "usage: make prod-restore-drill BACKUP=backups/file.dump" && exit 64)
	./scripts/prod_restore_drill.sh "$(BACKUP)"


staging-preflight:
	python3 scripts/staging_preflight.py

staging-build: staging-preflight
	docker compose --env-file .env.staging -f deploy/compose/production.yml build api

staging-up: staging-preflight
	docker compose --env-file .env.staging -f deploy/compose/production.yml up -d --build

staging-down:
	docker compose --env-file .env.staging -f deploy/compose/production.yml down

staging-logs:
	docker compose --env-file .env.staging -f deploy/compose/production.yml logs -f api ingress

staging-check:
	@test -n "$(BASE_URL)" || (echo "usage: make staging-check BASE_URL=https://api-staging.example.com" && exit 64)
	python3 scripts/check_secure_staging.py --base-url "$(BASE_URL)"


staging-wechat-evidence:
	@test -n "$(ORDER_ID)" || (echo "usage: make staging-wechat-evidence ORDER_ID=<uuid> EXPECT=payment|refund" && exit 64)
	@docker compose --env-file .env.staging -f deploy/compose/production.yml exec -T api 		python -m app.tools.wechat_acceptance --order-id "$(ORDER_ID)" --expect "$(or $(EXPECT),payment)"
