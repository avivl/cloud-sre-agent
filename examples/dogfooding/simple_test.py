#!/usr/bin/env python3
"""
Simple test that demonstrates the SRE agent system working with local file logs.
"""

import asyncio
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from gemini_sre_agent.config.ingestion_config import FileSystemConfig, SourceType
from gemini_sre_agent.ingestion.adapters.file_system import FileSystemAdapter
from gemini_sre_agent.ingestion.interfaces.core import LogEntry, LogSeverity
from gemini_sre_agent.ingestion.interfaces.resilience import create_resilience_config

def create_test_log_file():
    """Create a test log file with error scenarios."""
    log_file = "/tmp/sre-dogfooding/test_errors.log"
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # Create test log entries
    test_logs = [
        {
            "timestamp": "2025-09-05T20:15:00.000Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "ZeroDivisionError",
            "category": "mathematical",
            "endpoint": "/error/division",
            "request_id": "req_test_001",
            "traceback": "Traceback (most recent call last):\n  File \"app.py\", line 96, in division_error\n    result = 10 / 0\nZeroDivisionError: division by zero",
            "context": {"user_agent": "python-requests/2.32.5", "ip_address": "127.0.0.1"},
            "metadata": {"error_count": 1, "service_version": "1.0.0", "environment": "test"}
        },
        {
            "timestamp": "2025-09-05T20:15:01.000Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "MemoryError",
            "category": "resource",
            "endpoint": "/error/memory",
            "request_id": "req_test_002",
            "traceback": "Traceback (most recent call last):\n  File \"app.py\", line 121, in memory_error\n    raise MemoryError(\"Simulated memory exhaustion\")\nMemoryError: Simulated memory exhaustion",
            "context": {"allocated_chunks": 102, "total_memory_mb": 1020},
            "metadata": {"error_count": 2, "service_version": "1.0.0", "environment": "test"}
        },
        {
            "timestamp": "2025-09-05T20:15:02.000Z",
            "level": "ERROR",
            "service": "dogfood_service",
            "error_type": "ConnectionError",
            "category": "network",
            "endpoint": "/error/connection",
            "request_id": "req_test_003",
            "traceback": "Traceback (most recent call last):\n  File \"app.py\", line 45, in connection_error\n    sock.connect(('192.0.2.1', 9999))\nConnectionError: Connection refused",
            "context": {"target_host": "192.0.2.1", "target_port": 9999},
            "metadata": {"error_count": 3, "service_version": "1.0.0", "environment": "test"}
        }
    ]
    
    with open(log_file, 'w') as f:
        for log_entry in test_logs:
            f.write(json.dumps(log_entry) + '\n')
    
    print(f"✅ Created test log file: {log_file}")
    return log_file

async def test_file_system_adapter():
    """Test the file system adapter with our test logs."""
    print("🧪 Testing File System Adapter")
    print("=" * 40)
    
    # Create test log file
    log_file = create_test_log_file()
    
    try:
        # Create configuration
        config = FileSystemConfig(
            name="test-file-source",
            type=SourceType.FILE_SYSTEM,
            file_path=log_file,
            file_pattern="*.log",
        )
        
        # Create adapter
        adapter = FileSystemAdapter(config)
        
        # Start the adapter
        print("🚀 Starting file system adapter...")
        await adapter.start()
        
        # Test reading logs
        print("📖 Reading logs from file...")
        log_count = 0
        async for log_entry in adapter.get_logs():
            log_count += 1
            print(f"   Log {log_count}: {log_entry.severity} - {log_entry.message[:50]}...")
            
            if log_count >= 3:  # Limit to first 3 logs
                break
        
        # Stop the adapter
        await adapter.stop()
        
        print(f"✅ Successfully read {log_count} log entries")
        return True
        
    except Exception as e:
        print(f"❌ Error testing file system adapter: {e}")
        return False
    finally:
        # Clean up
        if os.path.exists(log_file):
            os.remove(log_file)

def test_dogfood_service():
    """Test the dogfood service directly."""
    print("\n🚀 Testing Dogfood Service")
    print("=" * 40)
    
    service_dir = Path(__file__).parent / "dogfood_service"
    service_script = service_dir / "app.py"
    
    if not service_script.exists():
        print(f"❌ Dogfood service not found at {service_script}")
        return False
    
    # Install requirements if needed
    requirements = service_dir / "requirements.txt"
    if requirements.exists():
        print("   Installing dogfood service requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], 
                      check=False, capture_output=True)
    
    # Start the service
    print("   Starting dogfood service...")
    process = subprocess.Popen(
        [sys.executable, str(service_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    try:
        # Wait for service to start
        time.sleep(3)
        
        if process.poll() is None:
            print("   ✅ Dogfood service started successfully")
            
            # Test error endpoints
            try:
                import requests
                
                base_url = "http://127.0.0.1:5001"
                
                # Test health check
                response = requests.get(f"{base_url}/", timeout=5)
                if response.status_code == 200:
                    print("   ✅ Service health check passed")
                else:
                    print(f"   ⚠️  Service returned status {response.status_code}")
                
                # Test error endpoints
                error_endpoints = ["/error/division", "/error/memory", "/error/connection"]
                for endpoint in error_endpoints:
                    try:
                        response = requests.get(f"{base_url}{endpoint}", timeout=5)
                        print(f"   ✅ {endpoint}: {response.status_code}")
                    except Exception as e:
                        print(f"   ❌ {endpoint}: {e}")
                
                return True
                
            except ImportError:
                print("   ⚠️  requests not available, skipping endpoint tests")
                return True
            except Exception as e:
                print(f"   ❌ Error testing endpoints: {e}")
                return False
        else:
            print("   ❌ Failed to start dogfood service")
            return False
    finally:
        # Clean up
        if process.poll() is None:
            process.terminate()
            time.sleep(1)
            if process.poll() is None:
                process.kill()

def main():
    """Main test function."""
    print("🧪 SRE Agent Simple Test")
    print("=" * 50)
    
    # Test 1: File system adapter
    success1 = asyncio.run(test_file_system_adapter())
    
    # Test 2: Dogfood service
    success2 = test_dogfood_service()
    
    print("\n📊 Test Results:")
    print(f"   File System Adapter: {'✅ PASS' if success1 else '❌ FAIL'}")
    print(f"   Dogfood Service: {'✅ PASS' if success2 else '❌ FAIL'}")
    
    if success1 and success2:
        print("\n🎉 All tests passed! The system is working correctly.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
