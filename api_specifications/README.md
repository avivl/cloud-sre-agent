# API Specifications

This directory contains OpenAPI 3.0 specifications for all APIs in the Gemini SRE Agent system.

## Available Specifications

### 1. Main System API (`openapi.yaml`)
Comprehensive API specification for the Gemini SRE Agent system including:
- Health monitoring and status endpoints
- Dashboard and overview endpoints
- Metrics and performance data endpoints
- Performance monitoring and analytics endpoints
- Cost analytics and spending endpoints
- Alert and notification endpoints
- System status and monitoring endpoints

**Base URL:** `https://api.gemini-sre-agent.com/v1`

### 2. Dogfooding Service API (`dogfooding-service-openapi.yaml`)
Flask-based error-producing service for testing SRE Agent capabilities:
- Health check endpoints
- Service status endpoints
- Error testing endpoints (intentionally trigger various error types)

**Base URL:** `http://localhost:5001`

## Error Types Tested

The dogfooding service provides endpoints to test the following error types:

1. **Mathematical Errors**
   - `GET /error/division` - ZeroDivisionError

2. **Resource Errors**
   - `GET /error/memory` - MemoryError (with safety limits)

3. **Network Errors**
   - `GET /error/timeout` - TimeoutError
   - `GET /error/connection` - ConnectionError

4. **Data Errors**
   - `GET /error/json` - JSONDecodeError
   - `GET /error/validation` - ValueError
   - `GET /error/key` - KeyError
   - `GET /error/index` - IndexError

5. **Filesystem Errors**
   - `GET /error/file` - FileNotFoundError
   - `GET /error/permission` - PermissionError

6. **Code Errors**
   - `GET /error/attribute` - AttributeError
   - `GET /error/type` - TypeError
   - `GET /error/recursion` - RecursionError

7. **Dependency Errors**
   - `GET /error/import` - ImportError

8. **Service Errors**
   - `GET /error/database` - Database connection error
   - `GET /error/rate_limit` - Rate limiting error

## Usage

### Viewing Specifications

You can view these specifications using any OpenAPI-compatible tool:

1. **Swagger UI**: Upload the YAML files to [swagger.io](https://editor.swagger.io/)
2. **Redoc**: Use [redoc.ly](https://redoc.ly/) to generate documentation
3. **Postman**: Import the specifications directly into Postman

### Code Generation

Use these specifications to generate client SDKs:

```bash
# Generate Python client
openapi-generator generate -i openapi.yaml -g python -o ./generated/python-client

# Generate TypeScript client
openapi-generator generate -i openapi.yaml -g typescript-axios -o ./generated/typescript-client

# Generate Go client
openapi-generator generate -i openapi.yaml -g go -o ./generated/go-client
```

### Validation

Validate the specifications:

```bash
# Using swagger-codegen
swagger-codegen validate -i openapi.yaml

# Using openapi-generator
openapi-generator validate -i openapi.yaml
```

## Authentication

The main system API supports two authentication methods:

1. **API Key**: Include `X-API-Key` header
2. **Bearer Token**: Include `Authorization: Bearer <token>` header

The dogfooding service does not require authentication.

## Rate Limiting

- Main API: Rate limits are provider-specific and managed by the underlying LLM providers
- Dogfooding Service: No rate limiting (intended for testing)

## Error Handling

All APIs return structured error responses with:
- HTTP status codes
- Error messages
- Timestamps
- Additional context when available

## Monitoring

All APIs include comprehensive monitoring capabilities:
- Health checks
- Performance metrics
- Cost analytics
- Alert systems
- Structured logging

## Contributing

When adding new API endpoints:

1. Update the appropriate OpenAPI specification
2. Add comprehensive schema definitions
3. Include example requests/responses
4. Update this README if adding new services
5. Test the specification using validation tools
