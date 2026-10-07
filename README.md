# Bulk Certificate Generator Backend

Backend API for generating personalized certificates in bulk.

## Project Status

Infrastructure setup complete. See documentation for setup and usage instructions.

## Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.12+

### Setup

1. Clone the repository
2. Copy `.env.example` to `.env` and configure as needed
3. Start services:
```bash
docker-compose up -d
```

4. Access the API at http://localhost:8000
5. View API documentation at http://localhost:8000/docs

## Development

### Project Structure

```
certificate-generator/
├── app/                    # Application code
│   ├── api/               # API routes
│   ├── core/              # Core configuration
│   ├── models/            # Database models
│   ├── schemas/           # Pydantic schemas
│   ├── services/          # Business logic
│   ├── tasks/             # Celery tasks
│   └── templates/         # Certificate templates
├── tests/                 # Test suite
├── alembic/              # Database migrations
└── data/certificates/    # Generated certificates

```

### Running Tests

```bash
docker-compose run --rm api pytest -v
```

### Database Migrations

```bash
# Generate a new migration
docker-compose exec api alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec api alembic upgrade head
```

## Documentation

Complete documentation will be added in future iterations.
