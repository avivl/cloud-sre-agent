#!/usr/bin/env python3
"""
Quick Test for SRE Agent System

This script quickly tests if the SRE agents are working properly.
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path


def test_sre_agent(single_agent=False):
    """Quick test of SRE agent functionality."""

    mode = "Single Agent" if single_agent else "Dual Agent"
    print(f"🧪 Quick SRE Agent Test ({mode})")
    print("=" * 30)

    # Clean up previous test artifacts
    print("🧹 Cleaning up previous test artifacts...")

    # Clean up log files
    log_dir = Path("/tmp/sre-dogfooding")
    if log_dir.exists():
        for log_file in log_dir.glob("*.log"):
            log_file.unlink()

    # Clean up real patches directory
    patches_dir = Path("/tmp/real_patches")
    if patches_dir.exists():
        for patch_file in patches_dir.glob("*.patch"):
            patch_file.unlink()
        print(f"   Cleaned {patches_dir}")
    else:
        # Create the directory if it doesn't exist
        patches_dir.mkdir(parents=True, exist_ok=True)
        print(f"   Created {patches_dir}")

    # Start the dogfooding demo
    print("1️⃣ Starting dogfooding demo...")
    demo_args = [sys.executable, "run_dogfood_demo.py"]
    if single_agent:
        demo_args.append("--single-agent")

    demo_process = subprocess.Popen(demo_args, cwd=Path(__file__).parent)

    try:
        # Wait for demo to complete
        print("⏳ Waiting for demo to complete...")
        time.sleep(25)  # Give demo time to complete and generate logs

        # Check if patches were generated
        patch_dir = Path("/tmp/real_patches")
        if patch_dir.exists():
            patch_files = list(patch_dir.glob("*.patch"))
            print(f"✅ Found {len(patch_files)} patches in /tmp/real_patches")
        else:
            print("❌ No patches found in /tmp/real_patches")

        # Check agent logs
        agent_log = Path("/tmp/sre-dogfooding/sre_agent_1.log")
        if agent_log.exists():
            with open(agent_log, "r") as f:
                content = f.read()

            # Count different types of log entries
            log_processing = content.count("[LOG_INGESTION] Processing log entry")
            analysis_ops = content.count("[ANALYSIS]")
            remediation_ops = content.count("[REMEDIATION]")
            errors = content.count("ERROR")

            print("\n📊 Agent Log Analysis:")
            print(f"   Log entries processed: {log_processing}")
            print(f"   Analysis operations: {analysis_ops}")
            print(f"   Remediation operations: {remediation_ops}")
            print(f"   Errors: {errors}")

            if errors > 0:
                print(f"\n❌ Found {errors} errors in agent log")
                print("   Last few error lines:")
                error_lines = [line for line in content.split("\n") if "ERROR" in line]
                for line in error_lines[-3:]:
                    print(f"   {line}")
            else:
                print("✅ No errors found in agent log")

        return True

    finally:
        # Clean up
        demo_process.terminate()
        time.sleep(1)


def main():
    """Main function with argument parsing."""
    parser = argparse.ArgumentParser(description="Quick SRE Agent Test")
    parser.add_argument(
        "--single-agent",
        action="store_true",
        help="Run with only the first agent (Fixer), skip the second agent (Meta-Monitor)",
    )

    args = parser.parse_args()
    test_sre_agent(single_agent=args.single_agent)


if __name__ == "__main__":
    main()
