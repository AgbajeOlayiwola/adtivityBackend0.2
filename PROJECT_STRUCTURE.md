# Adtivity Backend - Project Structure

##  Architecture Overview

The refactored Adtivity Backend follows modern Python application architecture patterns with clear separation of concerns, modular design, and improved maintainability.

##  Directory Structure

```
adtivityBackend0.2/
├── app/                          # Main application package
│   ├── __init__.py              # Package initialization and exports
│   ├── main.py                  # FastAPI application entry point
│   ├── core/                    # Core application modules
│   │   ├── __init__.py         # Core module exports
│   │   ├── config.py           # Configuration management
│   │   ├── database.py         # Database configuration
│   │   └── security.py         # Authentication & security
│   ├── api/                     # API route modules
│   │   ├── __init__.py         # API module exports
│   │   ├── auth.py             # Authentication endpoints
│   │   ├── dashboard.py        # Dashboard management
│   │   ├── sdk.py              # SDK event handling
│   │   ├── analytics.py        # Analytics endpoints
│   │   └── system.py           # System endpoints
│   ├── crud/                    # Database operations
│   │   ├── __init__.py         # CRUD module exports
│   │   ├── auth.py             # Auth-related operations
│   │   ├── users.py            # User management
│   │   ├── companies.py        # Company management
│   │   ├── events.py           # Event handling
│   │   └── metrics.py          # Metrics operations
│   ├── models.py                # SQLAlchemy models
│   ├── schemas.py               # Pydantic schemas
│   ├── redis_client.py          # Redis client
│   └── clickhouse_client.py     # ClickHouse client
├── tests/                       # Test suite
├── .env                         # Environment variables
├── .env.example                 # Environment template
├── requirements.txt              # Python dependencies
├── docker-compose.yml           # Docker services
├── alembic.ini                  # Database migrations
└── PROJECT_STRUCTURE.md         # This file
```

## Core Modules

### **Core Configuration (`app/core/`)**
- **`config.py`**: Centralized configuration using Pydantic settings
- **`database.py`**: Database connection and session management
- **`security.py`**: Authentication, authorization, and security utilities

### **API Routes (`app/api/`)**
- **`auth.py`**: User registration and authentication
- **`dashboard.py`**: Company and user management
- **`sdk.py`**: Client SDK event handling
- **`analytics.py`**: Metrics and analytics endpoints
- **`system.py`**: Health checks and system information

### **Database Operations (`app/crud/`)**
- **`auth.py`**: Password hashing and verification
- **`users.py`**: User CRUD operations
- **`companies.py`**: Company management operations
- **`events.py`**: Event processing and storage
- **`metrics.py`**: Analytics metrics operations

##  Key Improvements

### **1. Modular Architecture**
- **Separation of Concerns**: Each module has a single responsibility
- **Clean Imports**: Organized import structure with clear dependencies
- **Scalable Design**: Easy to add new features and modules

### **2. Modern Python Patterns**
- **Type Hints**: Comprehensive type annotations throughout
- **Async/Await**: Proper async support for better performance
- **Context Managers**: Proper resource management with lifespan

### **3. Enhanced Configuration**
- **Environment Variables**: Centralized configuration management
- **Validation**: Pydantic-based configuration validation
- **Security**: Environment-specific security settings

### **4. Improved Security**
- **Centralized Auth**: Single source of truth for authentication
- **Dependency Injection**: Clean dependency management
- **Error Handling**: Consistent error responses

### **5. Better Database Management**
- **Connection Pooling**: Optimized database connections
- **Query Logging**: Debug mode query performance monitoring
- **Transaction Management**: Proper rollback handling


##  Testing

### **Running Tests**
```bash
# Activate virtual environment
source .venv/bin/activate

# Run tests
pytest tests/

# Run with coverage
pytest --cov=app tests/
```

### **Test Structure**
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test API endpoints and database operations
- **End-to-End Tests**: Test complete user workflows


### **Running the Application**
```bash
# Development
uvicorn app.main:app --reload

# Production
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

### **Docker Deployment**
```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f
```

##  Performance Optimizations

### **Database**
- Connection pooling with automatic recycling
- Query performance monitoring in debug mode
- Optimized session management

### **Caching**
- Redis integration for session and data caching
- Configurable cache TTL and strategies

### **Async Operations**
- Non-blocking I/O operations
- Proper async/await patterns
- Background task processing

##  Security Features

### **Authentication**
- JWT-based token authentication
- Secure password hashing with bcrypt
- API key authentication for SDK endpoints

### **Authorization**
- Role-based access control
- Company-level data isolation
- Admin privilege management

### **Data Protection**
- Input validation with Pydantic
- SQL injection prevention
- XSS protection

## Monitoring & Logging

### **Application Metrics**
- Health check endpoints
- Performance monitoring
- Error tracking and logging

### **Database Monitoring**
- Query performance logging
- Connection pool statistics
- Slow query detection

