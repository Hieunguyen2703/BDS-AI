# Makefile for BDS Agent

.PHONY: help install dev test build deploy clean

help:
	@echo "BDS Agent - Available commands:"
	@echo ""
	@echo "  make install     - Install all dependencies"
	@echo "  make dev         - Start development environment"
	@echo "  make test        - Run all tests"
	@echo "  make build       - Build Docker images"
	@echo "  make deploy      - Deploy with Docker Compose"
	@echo "  make clean       - Clean up temporary files"
	@echo ""

# Install dependencies
install:
	pip install -r requirements.txt
	cd frontend && npm install

# Development
dev:
	docker compose up -d postgres redis
	@echo "Starting backend..."
	uvicorn api.main:app --reload &
	@echo "Starting frontend..."
	cd frontend && npm run dev

# Run backend only
backend:
	uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Run frontend only
frontend:
	cd frontend && npm run dev

# Database migrations
migrate:
	alembic upgrade head

# Create new migration
migration:
	alembic revision --autogenerate -m "$(msg)"

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=. --cov-report=html

test-frontend:
	cd frontend && npm test

test-e2e:
	cd frontend && npx playwright test

# Build
build:
	docker compose build

# Deploy
deploy:
	docker compose up -d

deploy-prod:
	docker compose --profile production up -d

# Stop all services
stop:
	docker compose down

# Clean up
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache htmlcov .coverage
	rm -rf frontend/.next frontend/node_modules
	docker compose down -v

# Logs
logs:
	docker compose logs -f

logs-backend:
	docker compose logs -f backend

logs-frontend:
	docker compose logs -f frontend

# Shell access
shell-backend:
	docker compose exec backend bash

shell-db:
	docker compose exec postgres psql -U postgres -d bds_agent

# Pull Ollama model
ollama-setup:
	ollama pull qwen2.5:14b
