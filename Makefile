.PHONY: dev prod test migrate lint clean seed-prompts

dev:
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up

prod:
	docker compose up --build

test:
	cd backend && python -m pytest tests/ -v --cov=app --cov-report=term-missing

migrate:
	cd backend && alembic upgrade head

lint:
	cd backend && ruff check app/ && mypy app/
	cd frontend && npx tsc --noEmit && npx eslint src/

seed-prompts:
	cd backend && python -c "from app.storage.database import init_db; import asyncio; asyncio.run(init_db())"

clean:
	docker compose down -v
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
