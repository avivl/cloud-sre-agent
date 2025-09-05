#!/usr/bin/env python3
"""
Dogfood Service - A Flask application that generates various types of errors
for testing the SRE agent system.
"""

import json
import random
import time
import traceback
from datetime import datetime
from flask import Flask, jsonify, request
from werkzeug.exceptions import InternalServerError

app = Flask(__name__)

# Global variables for state tracking
error_count = 0
memory_chunks = []

@app.route('/')
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "service": "dogfood_service",
        "version": "1.0.0"
    })

@app.route('/error/division')
def division_error():
    """Generate a ZeroDivisionError."""
    global error_count
    error_count += 1
    
    try:
        result = 10 / 0
        return jsonify({"result": result})
    except ZeroDivisionError as e:
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "ZeroDivisionError",
            "category": "mathematical",
            "endpoint": "/error/division",
            "request_id": f"req_{int(time.time() * 1000)}",
            "traceback": traceback.format_exc(),
            "context": {
                "user_agent": request.headers.get('User-Agent', 'unknown'),
                "ip_address": request.remote_addr
            },
            "metadata": {
                "error_count": error_count,
                "service_version": "1.0.0",
                "environment": "dogfood"
            }
        }
        
        print(json.dumps(error_data))
        raise InternalServerError("Division by zero error")

@app.route('/error/memory')
def memory_error():
    """Generate a MemoryError."""
    global error_count, memory_chunks
    error_count += 1
    
    try:
        # Simulate memory allocation
        for i in range(102):
            chunk = [0] * (1024 * 1024)  # 1MB chunk
            memory_chunks.append(chunk)
            if len(memory_chunks) > 100:  # Safety limit
                raise MemoryError("Simulated memory exhaustion (safety limit reached)")
        
        return jsonify({"allocated_mb": len(memory_chunks)})
    except MemoryError as e:
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "MemoryError",
            "category": "resource",
            "endpoint": "/error/memory",
            "request_id": f"req_{int(time.time() * 1000)}",
            "traceback": traceback.format_exc(),
            "context": {
                "allocated_chunks": len(memory_chunks),
                "total_memory_mb": len(memory_chunks)
            },
            "metadata": {
                "error_count": error_count,
                "service_version": "1.0.0",
                "environment": "dogfood"
            }
        }
        
        print(json.dumps(error_data))
        raise InternalServerError("Memory allocation error")

@app.route('/error/timeout')
def timeout_error():
    """Generate a timeout scenario."""
    global error_count
    error_count += 1
    
    # Simulate a long-running operation
    time.sleep(30)  # This will timeout
    
    return jsonify({"status": "completed"})

@app.route('/error/connection')
def connection_error():
    """Generate a connection error."""
    global error_count
    error_count += 1
    
    try:
        import socket
        # Try to connect to a non-existent service
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(('192.0.2.1', 9999))  # RFC 5737 test IP
    except Exception as e:
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "ConnectionError",
            "category": "network",
            "endpoint": "/error/connection",
            "request_id": f"req_{int(time.time() * 1000)}",
            "traceback": traceback.format_exc(),
            "context": {
                "target_host": "192.0.2.1",
                "target_port": 9999,
                "timeout": 1
            },
            "metadata": {
                "error_count": error_count,
                "service_version": "1.0.0",
                "environment": "dogfood"
            }
        }
        
        print(json.dumps(error_data))
        raise InternalServerError("Connection failed")

@app.route('/error/validation')
def validation_error():
    """Generate a validation error."""
    global error_count
    error_count += 1
    
    try:
        data = request.get_json()
        if not data or 'required_field' not in data:
            raise ValueError("Missing required field: 'required_field'")
        
        if not isinstance(data['required_field'], str):
            raise TypeError("Field 'required_field' must be a string")
        
        return jsonify({"status": "validated", "data": data})
    except (ValueError, TypeError) as e:
        error_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": type(e).__name__,
            "category": "validation",
            "endpoint": "/error/validation",
            "request_id": f"req_{int(time.time() * 1000)}",
            "traceback": traceback.format_exc(),
            "context": {
                "received_data": data if 'data' in locals() else None,
                "user_agent": request.headers.get('User-Agent', 'unknown')
            },
            "metadata": {
                "error_count": error_count,
                "service_version": "1.0.0",
                "environment": "dogfood"
            }
        }
        
        print(json.dumps(error_data))
        raise InternalServerError("Validation failed")

@app.route('/error/random')
def random_error():
    """Generate a random error from the available types."""
    error_types = ['division', 'memory', 'connection', 'validation']
    error_type = random.choice(error_types)
    
    if error_type == 'division':
        return division_error()
    elif error_type == 'memory':
        return memory_error()
    elif error_type == 'connection':
        return connection_error()
    elif error_type == 'validation':
        return validation_error()

@app.route('/status')
def status():
    """Get current service status."""
    return jsonify({
        "status": "running",
        "error_count": error_count,
        "memory_chunks": len(memory_chunks),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

if __name__ == '__main__':
    print("Starting Dogfood Service...")
    print("Available endpoints:")
    print("  GET  /              - Health check")
    print("  GET  /error/division - Division by zero error")
    print("  GET  /error/memory   - Memory allocation error")
    print("  GET  /error/timeout  - Timeout error (30s)")
    print("  GET  /error/connection - Connection error")
    print("  GET  /error/validation - Validation error")
    print("  GET  /error/random   - Random error")
    print("  GET  /status        - Service status")
    print("\nStarting server on http://127.0.0.1:5001")
    
    app.run(host='0.0.0.0', port=5001, debug=True)
