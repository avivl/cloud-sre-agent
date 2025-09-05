#!/usr/bin/env python3
"""
Quick Test Script for SRE Agent Dogfooding
Tests the SRE agent system with a simple error scenario.
"""

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

def cleanup_directories():
    """Clean up log and patch directories."""
    print("🧹 Cleaning up directories...")
    
    # Clean log directory
    log_dir = Path("/tmp/sre-dogfooding")
    if log_dir.exists():
        for file in log_dir.glob("*.log"):
            file.unlink()
        print(f"   Cleaned log directory: {log_dir}")
    
    # Clean patch directory
    patch_dir = Path("/tmp/real_patches")
    if patch_dir.exists():
        for file in patch_dir.glob("*.json"):
            file.unlink()
        print(f"   Cleaned patch directory: {patch_dir}")
    else:
        patch_dir.mkdir(parents=True, exist_ok=True)
        print(f"   Created patch directory: {patch_dir}")

def start_dogfood_service():
    """Start the dogfood service."""
    print("🚀 Starting dogfood service...")
    
    service_dir = Path(__file__).parent / "dogfood_service"
    service_script = service_dir / "app.py"
    
    if not service_script.exists():
        print(f"❌ Dogfood service not found at {service_script}")
        return None
    
    # Install requirements if needed
    requirements = service_dir / "requirements.txt"
    if requirements.exists():
        print("   Installing dogfood service requirements...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(requirements)], 
                      check=False, capture_output=True)
    
    # Start the service
    process = subprocess.Popen(
        [sys.executable, str(service_script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait a moment for the service to start
    time.sleep(3)
    
    if process.poll() is None:
        print("   ✅ Dogfood service started successfully")
        return process
    else:
        print("   ❌ Failed to start dogfood service")
        return None

def start_sre_agent(config_file, agent_name):
    """Start an SRE agent with the given configuration."""
    print(f"🤖 Starting {agent_name}...")
    
    config_path = Path(__file__).parent / "configs" / config_file
    if not config_path.exists():
        print(f"❌ Config file not found: {config_path}")
        return None
    
    # Start the SRE agent
    process = subprocess.Popen(
        [sys.executable, "main.py", "--config", str(config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    
    # Wait a moment for the agent to start
    time.sleep(2)
    
    if process.poll() is None:
        print(f"   ✅ {agent_name} started successfully")
        return process
    else:
        print(f"   ❌ Failed to start {agent_name}")
        return None

def trigger_errors():
    """Trigger various error scenarios in the dogfood service."""
    print("🔥 Triggering error scenarios...")
    
    import requests
    
    base_url = "http://127.0.0.1:5001"
    
    # Test health check first
    try:
        response = requests.get(f"{base_url}/", timeout=5)
        if response.status_code == 200:
            print("   ✅ Service is healthy")
        else:
            print(f"   ⚠️  Service returned status {response.status_code}")
    except Exception as e:
        print(f"   ❌ Service health check failed: {e}")
        return
    
    # Trigger various errors
    error_endpoints = [
        "/error/division",
        "/error/memory", 
        "/error/connection",
        "/error/validation",
        "/error/random"
    ]
    
    for endpoint in error_endpoints:
        try:
            print(f"   Triggering {endpoint}...")
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            print(f"     Status: {response.status_code}")
        except Exception as e:
            print(f"     Error: {e}")
        
        time.sleep(1)  # Brief pause between errors

def analyze_logs():
    """Analyze the generated logs."""
    print("\n📊 Agent Log Analysis:")
    
    log_dir = Path("/tmp/sre-dogfooding")
    if not log_dir.exists():
        print("   ❌ Log directory not found")
        return
    
    # Count log entries
    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print("   ❌ No log files found")
        return
    
    total_entries = 0
    error_count = 0
    
    for log_file in log_files:
        print(f"\n   📄 {log_file.name}:")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            
            entries = 0
            errors = 0
            
            for line in lines:
                if line.strip():
                    entries += 1
                    try:
                        log_entry = json.loads(line)
                        if log_entry.get('level') == 'ERROR':
                            errors += 1
                    except json.JSONDecodeError:
                        # Not a JSON log entry, check for error keywords
                        if any(keyword in line.lower() for keyword in ['error', 'exception', 'traceback']):
                            errors += 1
                    except:
                        pass
            
            print(f"     Log entries: {entries}")
            print(f"     Errors: {errors}")
            
            total_entries += entries
            error_count += errors
            
        except Exception as e:
            print(f"     Error reading log: {e}")
    
    print(f"\n   📈 Summary:")
    print(f"     Total log entries: {total_entries}")
    print(f"     Total errors: {error_count}")
    
    if error_count > 0:
        print(f"     ✅ Found {error_count} errors in agent log")
    else:
        print(f"     ⚠️  No errors found in agent log")

def check_patches():
    """Check for generated patches."""
    print("\n🔧 Patch Analysis:")
    
    patch_dir = Path("/tmp/real_patches")
    if not patch_dir.exists():
        print("   ❌ Patch directory not found")
        return
    
    patch_files = list(patch_dir.glob("*.json"))
    if not patch_files:
        print("   ❌ No patch files found")
        return
    
    print(f"   📄 Found {len(patch_files)} patch files:")
    for patch_file in patch_files:
        try:
            with open(patch_file, 'r') as f:
                patch_data = json.load(f)
            
            print(f"     - {patch_file.name}")
            print(f"       Issue: {patch_data.get('issue_title', 'Unknown')}")
            print(f"       Status: {patch_data.get('status', 'Unknown')}")
        except Exception as e:
            print(f"     - {patch_file.name} (Error reading: {e})")

def main():
    """Main test function."""
    print("🧪 SRE Agent Quick Test")
    print("=" * 50)
    
    # Parse command line arguments
    single_agent = "--single-agent" in sys.argv
    
    # Clean up first
    cleanup_directories()
    
    # Start services
    dogfood_process = start_dogfood_service()
    if not dogfood_process:
        print("❌ Cannot proceed without dogfood service")
        return 1
    
    # Start SRE agents
    agent1_process = start_sre_agent("dogfood_instance_1.yaml", "SRE Agent 1")
    if not agent1_process:
        print("❌ Cannot proceed without SRE Agent 1")
        dogfood_process.terminate()
        return 1
    
    agent2_process = None
    if not single_agent:
        agent2_process = start_sre_agent("dogfood_instance_2.yaml", "SRE Agent 2")
        if not agent2_process:
            print("⚠️  SRE Agent 2 failed to start, continuing with single agent")
    
    try:
        # Wait for agents to initialize
        print("\n⏳ Waiting for agents to initialize...")
        time.sleep(5)
        
        # Trigger errors
        trigger_errors()
        
        # Wait for processing
        print("\n⏳ Waiting for agents to process logs...")
        time.sleep(10)
        
        # Analyze results
        analyze_logs()
        check_patches()
        
        print("\n✅ Quick test completed!")
        
    except KeyboardInterrupt:
        print("\n⚠️  Test interrupted by user")
    finally:
        # Cleanup
        print("\n🧹 Cleaning up processes...")
        
        if agent2_process:
            agent2_process.terminate()
        if agent1_process:
            agent1_process.terminate()
        if dogfood_process:
            dogfood_process.terminate()
        
        # Wait for processes to terminate
        time.sleep(2)
        
        # Force kill if needed
        for process in [agent2_process, agent1_process, dogfood_process]:
            if process and process.poll() is None:
                process.kill()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
