#!/usr/bin/env python3
"""
Dogfooding Demo Orchestration Script

Manages the entire dogfooding environment including:
- Problem Service (Flask app)
- SRE Agent Instance #1 (Fixer)
- SRE Agent Instance #2 (Meta-Monitor)

Automatically runs all error scenarios and calculates runtime based on scenario count.
All files must be under 250 LOC for maintainability.
"""

import argparse
import asyncio
import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Dict

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Global process tracking
processes: Dict[str, subprocess.Popen] = {}


class DogfoodOrchestrator:
    """Orchestrates the dogfooding environment."""

    def __init__(self, single_agent=False):
        self.scenarios = ["division", "memory", "timeout", "json"]
        self.base_dir = Path(__file__).parent
        self.service_dir = self.base_dir / "dogfood_service"
        self.config_dir = self.base_dir / "configs"
        self.log_dir = Path("/tmp/sre-dogfooding")
        self.single_agent = single_agent

    async def setup_environment(self) -> bool:
        """Set up the dogfooding environment."""
        try:
            logger.info("Setting up dogfooding environment...")

            # Create log directory and files
            self.log_dir.mkdir(exist_ok=True)

            # Determine which log files to create based on mode
            log_files = ["dogfood_service.log", "sre_agent_1.log"]
            if not self.single_agent:
                log_files.append("sre_agent_2.log")

            for log_file in log_files:
                log_path = self.log_dir / log_file
                if log_path.exists():
                    # Clean existing log file
                    size_before = log_path.stat().st_size
                    log_path.write_text("")
                    logger.info(f"Cleaned log file: {log_file} ({size_before} bytes)")
                else:
                    # Create empty log file
                    log_path.touch()
                    logger.info(f"Created log file: {log_path}")

            # Install service dependencies using uv
            requirements_file = self.service_dir / "requirements.txt"
            if requirements_file.exists():
                logger.info("Installing service dependencies with uv...")
                # Use the virtual environment Python if available
                venv_python = self.base_dir.parent.parent / ".venv" / "bin" / "python"
                python_executable = (
                    str(venv_python) if venv_python.exists() else sys.executable
                )

                result = subprocess.run(
                    [
                        "uv",
                        "pip",
                        "install",
                        "-r",
                        str(requirements_file),
                        "--python",
                        python_executable,
                    ],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    logger.error(f"Failed to install dependencies: {result.stderr}")
                    return False

            # Validate configuration files
            config_files = [
                self.config_dir / "dogfood_instance_1.yaml",
                self.config_dir / "dogfood_instance_2.yaml",
            ]
            for config_file in config_files:
                if not config_file.exists():
                    logger.error(f"Configuration file not found: {config_file}")
                    return False

            logger.info("Environment setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Environment setup failed: {e}")
            return False

    async def start_service(self) -> bool:
        """Start the Problem Service."""
        try:
            logger.info("Starting Problem Service...")
            service_script = self.service_dir / "app.py"

            # Use the virtual environment Python if available
            venv_python = self.base_dir.parent.parent / ".venv" / "bin" / "python"
            python_executable = (
                str(venv_python) if venv_python.exists() else sys.executable
            )

            process = subprocess.Popen(
                [python_executable, str(service_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            processes["service"] = process

            # Wait for service to be ready
            await asyncio.sleep(3)

            # Health check
            try:
                import requests

                logger.info("Performing health check...")
                response = requests.get("http://localhost:5001/", timeout=5)
                logger.info(f"Health check response: {response.status_code}")
                if response.status_code == 200:
                    logger.info("Problem Service started successfully")
                    return True
                else:
                    logger.error(
                        f"Health check failed with status {response.status_code}"
                    )
                    return False
            except ImportError:
                logger.warning("requests not available, skipping health check")
                return True
            except Exception as e:
                logger.error(f"Health check failed: {e}")
                return False

            return False

        except Exception as e:
            logger.error(f"Failed to start service: {e}")
            return False

    async def start_agent(self, instance_num: int) -> bool:
        """Start an SRE Agent instance."""
        try:
            config_file = self.config_dir / f"dogfood_instance_{instance_num}.yaml"
            log_file = self.log_dir / f"sre_agent_{instance_num}.log"

            logger.info(f"Starting SRE Agent Instance #{instance_num}...")

            # Set environment variables
            env = os.environ.copy()
            env["USE_NEW_INGESTION_SYSTEM"] = "true"

            # Use the virtual environment Python if available
            venv_python = self.base_dir.parent.parent / ".venv" / "bin" / "python"
            python_executable = (
                str(venv_python) if venv_python.exists() else sys.executable
            )

            # Use new ingestion system config for both instances
            if instance_num == 1:
                config_file = self.config_dir / "dogfood_instance_1.yaml"
                main_script = "main.py"
            else:
                # Use new ingestion system for instance 2 as well
                config_file = self.config_dir / "dogfood_instance_2.yaml"
                main_script = "main.py"

            # Build command arguments
            cmd_args = [
                python_executable,
                main_script,
                "--config-file",
                str(config_file),
            ]

            # Add single-agent flag if in single-agent mode
            if self.single_agent:
                cmd_args.append("--single-agent")

            process = subprocess.Popen(
                cmd_args,
                stdout=open(log_file, "w"),
                stderr=subprocess.STDOUT,
                text=True,
                env=env,
                cwd=self.base_dir.parent.parent,
            )

            processes[f"agent_{instance_num}"] = process

            # Wait for agent to initialize
            await asyncio.sleep(5)

            logger.info(f"SRE Agent Instance #{instance_num} started")
            return True

        except Exception as e:
            logger.error(f"Failed to start agent {instance_num}: {e}")
            return False

    async def trigger_error_scenarios(self) -> None:
        """Trigger error scenarios and calculate runtime automatically."""
        logger.info("Triggering error scenarios...")

        try:
            import requests

            base_url = "http://localhost:5001"

            for i, scenario in enumerate(self.scenarios):
                logger.info(f"Triggering {scenario} error...")
                try:
                    response = requests.get(f"{base_url}/error/{scenario}", timeout=10)
                    logger.info(f"Scenario {scenario}: Status {response.status_code}")
                except requests.exceptions.RequestException as e:
                    logger.info(f"Scenario {scenario}: Expected error - {e}")

                # Wait between scenarios (except for the last one)
                if i < len(self.scenarios) - 1:
                    await asyncio.sleep(2)

        except ImportError:
            logger.warning("requests not available, skipping error scenarios")

    def calculate_runtime(self) -> int:
        """Calculate runtime based on number of scenarios."""
        # Base time: 10 seconds for startup + 2 seconds per scenario + 5 seconds buffer
        base_time = 10
        scenario_time = len(self.scenarios) * 2
        buffer_time = 5
        return base_time + scenario_time + buffer_time

    async def monitor_processes(self) -> None:
        """Monitor all processes and restart if needed."""
        while True:
            for name, process in processes.items():
                if process.poll() is not None:
                    logger.error(f"Process {name} has stopped unexpectedly")
                    # In a real implementation, you might want to restart here

            await asyncio.sleep(10)  # Check every 10 seconds

    async def cleanup(self) -> None:
        """Clean up all processes and resources."""
        logger.info("Cleaning up dogfooding environment...")

        for name, process in processes.items():
            try:
                process.terminate()
                process.wait(timeout=5)
                logger.info(f"Terminated {name}")
            except subprocess.TimeoutExpired:
                process.kill()
                logger.warning(f"Force killed {name}")
            except Exception as e:
                logger.error(f"Error terminating {name}: {e}")

        processes.clear()
        logger.info("Cleanup completed")


async def main():
    """Main orchestration function."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Dogfooding Demo Orchestration")
    parser.add_argument(
        "--single-agent",
        action="store_true",
        help="Run with only the first agent (Fixer), skip the second agent (Meta-Monitor)",
    )

    args = parser.parse_args()
    orchestrator = DogfoodOrchestrator(single_agent=args.single_agent)

    # Set up signal handlers for graceful shutdown
    def signal_handler(signum, frame):
        logger.info("Received shutdown signal")
        asyncio.create_task(orchestrator.cleanup())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Setup environment
        if not await orchestrator.setup_environment():
            logger.error("Environment setup failed")
            return 1

        # Start services
        if not await orchestrator.start_service():
            logger.error("Failed to start Problem Service")
            return 1

        if not await orchestrator.start_agent(1):
            logger.error("Failed to start Agent Instance #1")
            return 1

        # Only start the second agent if not in single-agent mode
        if not orchestrator.single_agent:
            if not await orchestrator.start_agent(2):
                logger.error("Failed to start Agent Instance #2")
                return 1
        else:
            logger.info("Single-agent mode: Skipping Agent Instance #2 (Meta-Monitor)")

        logger.info("All services started successfully")

        # Run demo mode with calculated runtime
        await orchestrator.trigger_error_scenarios()

        # Calculate runtime based on number of scenarios
        runtime = orchestrator.calculate_runtime()
        logger.info(f"Demo completed. Running for {runtime} seconds total.")
        await asyncio.sleep(runtime)

    except KeyboardInterrupt:
        logger.info("Demo interrupted by user")
    except Exception as e:
        logger.error(f"Orchestration failed: {e}")
        return 1
    finally:
        await orchestrator.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
