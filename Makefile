.PHONY: dev migrate seed test clean

dev:
	docker-compose -f docker-compose.yml up --build

migrate:
	cd backend && alembic upgrade head && python -c "import asyncio; from app.storage.database import init_db; asyncio.run(init_db())"

seed:
	cd backend && python scripts/seed.py

test:
	cd backend && PYTHONPATH=. pytest tests/ -v

clean:
	docker-compose down -v
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
