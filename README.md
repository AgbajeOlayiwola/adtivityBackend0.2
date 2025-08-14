#  Adtivity Backend

[![Python](https://img.shields.io/badge/Python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.116+-green.svg)](https://fastapi.tiangolo.com/)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> **A modern, scalable multi-tenant analytics platform for Web2 and Web3 applications**

Adtivity Backend is a production-ready FastAPI application that provides comprehensive analytics capabilities for both traditional web applications and blockchain-based applications. Built with modern Python practices, it offers a robust foundation for collecting, processing, and analyzing user events and blockchain transactions.

## Features

### **Multi-Tenant Architecture**
- **Platform Users**: Dashboard users managing multiple client companies
- **Client Companies**: Companies using your SDK with secure API key authentication
- **Data Isolation**: Complete separation of data between different companies

###  **Analytics Engine**
- **Web2 Events**: Standard analytics (page views, user actions, conversions)
- **Web3 Events**: Blockchain transactions, wallet interactions, smart contract events
- **Real-time Processing**: Immediate event ingestion and processing
- **Flexible Metrics**: Customizable analytics and business metrics

###  **Enterprise Security**
- **JWT Authentication**: Secure token-based authentication for dashboard users
- **API Key Security**: Hash-based API key validation for client SDKs
- **Role-based Access**: Admin privileges and company-level permissions
- **Data Encryption**: Secure password hashing with bcrypt

### **Performance & Scalability**
- **Async Operations**: Non-blocking I/O with FastAPI
- **Connection Pooling**: Optimized database connections
- **Redis Integration**: Caching and session management
- **Horizontal Scaling**: Modular architecture for easy scaling

##  Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client SDKs   │    │   Dashboard     │    │   Analytics     │
│   (Web2/Web3)   │    │   Users         │    │   Engine        │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                    FastAPI Application                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌──────────┐  │
│  │   Auth API  │ │ Dashboard   │ │   SDK API   │ │ Analytics│  │
│  │             │ │    API      │ │             │ │    API   │  │
│  └─────────────┘ └─────────────┘ └─────────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │                      │                      │
          │                      │                      │
          ▼                      ▼                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │   ClickHouse    │
│   (Main Data)   │    │   (Caching)     │    │   (Analytics)   │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

##  Quick Start

### Prerequisites

- **Python 3.13+**
- **PostgreSQL 14+**
- **Redis 7+**
- **ClickHouse** (optional, for advanced analytics)
- **Docker & Docker Compose** (recommended)

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/adtivity-backend.git
cd adtivity-backend
```

### 2. Environment Setup

```bash
# Copy environment template
cp .env.example .env

# Edit environment variables
nano .env
```

**Required Environment Variables:**
```env
# Database
DATABASE_URL=postgresql+psycopg2://username:password@localhost/adtivity

# Security (Change in production!)
SECRET_KEY=your-very-secure-and-long-secret-key-that-you-should-change-in-production

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# ClickHouse (optional)
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
```

### 3. Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # Linux/Mac
# or
.venv\Scripts\activate     # Windows
```

### 4. Install Dependencies

```bash
pip install -r requirements.txt
```

### 5. Database Setup

```bash
# Start PostgreSQL and Redis
docker-compose up -d postgres redis

# Initialize database
python -c "from app.core.database import init_db; init_db()"
```

### 6. Run the Application

```bash
# Development mode
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### 7. Access the API

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/system/health
- **Root Endpoint**: http://localhost:8000/

## API Documentation

### Authentication Endpoints

```http
POST /auth/register          # Register new platform user
POST /auth/token            # Login and get JWT token
```

### Dashboard Management

```http
GET    /dashboard/me                                    # Get current user profile
POST   /dashboard/client-companies/                     # Create new company
GET    /dashboard/client-companies/                     # List user's companies
GET    /dashboard/client-companies/{id}/events          # Get company events
GET    /dashboard/client-companies/{id}/web3-events     # Get Web3 events
DELETE /dashboard/client-companies/{id}                 # Delete company
```

### SDK Integration

```http
POST /sdk/event              # Send events from client applications
```

### Analytics

```http
POST /analytics/metrics/      # Record platform metrics
GET  /analytics/metrics/      # Retrieve analytics data
```

### System

```http
GET /system/health            # Health check
GET /system/info              # System information
```

## Development

### Project Structure

```
app/
├── core/           # Core application modules
│   ├── config.py   # Configuration management
│   ├── database.py # Database configuration
│   └── security.py # Authentication & security
├── api/            # API route modules
│   ├── auth.py     # Authentication endpoints
│   ├── dashboard.py # Dashboard management
│   ├── sdk.py      # SDK event handling
│   ├── analytics.py # Analytics endpoints
│   └── system.py   # System endpoints
├── crud/           # Database operations
│   ├── auth.py     # Auth operations
│   ├── users.py    # User management
│   ├── companies.py # Company management
│   ├── events.py   # Event handling
│   └── metrics.py  # Metrics operations
├── models.py       # SQLAlchemy models
├── schemas.py      # Pydantic schemas
└── main.py         # FastAPI application
```

### Adding New Features

1. **Create API Endpoints**: Add routes in `app/api/`
2. **Database Operations**: Implement CRUD functions in `app/crud/`
3. **Data Models**: Define models in `models.py` and schemas in `schemas.py`
4. **Configuration**: Add settings in `app/core/config.py`

## Docker Deployment

### Quick Start with Docker

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Production Dockerfile

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["gunicorn", "app.main:app", "-w", "4", "-k", "uvicorn.workers.UvicornWorker"]
```

## Monitoring & Health Checks

### Health Endpoints

- **`/system/health`**: Basic application health
- **`/system/info`**: System configuration and status

### Database Monitoring

- Connection pool statistics
- Query performance logging (debug mode)
- Slow query detection

### Logging

- Structured logging with different levels
- Request/response logging
- Error tracking and debugging

##  Security Features

### Authentication

- **JWT Tokens**: Secure, time-limited access tokens
- **API Keys**: Hash-based validation for SDK authentication
- **Password Security**: bcrypt hashing with salt

### Authorization

- **Role-based Access**: Admin and user privileges
- **Company Isolation**: Data separation between tenants
- **Resource Protection**: Endpoint-level access control

### Data Protection

- **Input Validation**: Pydantic-based request validation
- **SQL Injection Prevention**: Parameterized queries
- **XSS Protection**: Content security headers

## Performance Optimization

### Database

- Connection pooling with automatic recycling
- Query optimization and indexing
- Read replicas for analytics queries

### Caching

- Redis for session storage
- API response caching
- Database query result caching

### Async Operations

- Non-blocking I/O operations
- Background task processing
- Event-driven architecture

## Support

### Getting Help

- **Documentation**: [API Docs](http://localhost:8000/docs)
