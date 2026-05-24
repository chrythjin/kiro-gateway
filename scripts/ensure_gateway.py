#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ensure Kiro Gateway is running before launching another command.

This helper is intended for OpenCode wrappers and shell aliases. It starts the
gateway once in the background, records the process id, and then optionally
executes the command supplied after ``--``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from dataclasses import dataclass
from http.client import HTTPResponse
from pathlib import Path
from typing import cast

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_TIMEOUT_SECONDS = 20.0
DEFAULT_POLL_INTERVAL_SECONDS = 0.25


@dataclass(frozen=True)
class GatewayConfig:
    """Configuration for locating and starting Kiro Gateway.

    Args:
        gateway_dir: Repository root containing ``main.py``.
        python_executable: Python executable used to start the gateway.
        host: Host passed to ``main.py --host`` and used for health checks.
        port: Port passed to ``main.py --port`` and used for health checks.
        timeout_seconds: Maximum time to wait for the health endpoint.
        poll_interval_seconds: Delay between health check attempts.
        health_path: HTTP path used to verify the gateway is ready.
        pid_file: File where the background process id is written.
        log_file: File where stdout and stderr from the gateway are appended.
        dry_run: When true, print the start command without launching it.
    """

    gateway_dir: Path
    python_executable: str
    host: str
    port: int
    timeout_seconds: float
    poll_interval_seconds: float
    health_path: str
    pid_file: Path
    log_file: Path
    dry_run: bool = False

    @property
    def health_url(self) -> str:
        """Return the local health check URL for this gateway instance."""

        return f"http://{self.host}:{self.port}{self.health_path}"

    @property
    def start_command(self) -> list[str]:
        """Return the command used to start the gateway in the background."""

        return [
            self.python_executable,
            "main.py",
            "--host",
            self.host,
            "--port",
            str(self.port),
        ]


def is_process_alive(pid: int) -> bool:
    """Return whether a process id appears to still be alive.

    Args:
        pid: Operating system process id.

    Returns:
        True when the process exists, otherwise False.
    """

    if pid <= 0:
        return False

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def read_pid_file(pid_file: Path) -> int | None:
    """Read a PID file if it contains a valid integer.

    Args:
        pid_file: Path to the PID file.

    Returns:
        Parsed process id, or None when missing or malformed.
    """

    try:
        return int(pid_file.read_text(encoding="utf-8").strip())
    except FileNotFoundError:
        return None
    except ValueError:
        return None


def remove_stale_pid_file(pid_file: Path) -> None:
    """Remove a stale PID file if it exists.

    Args:
        pid_file: Path to remove.
    """

    try:
        pid_file.unlink()
    except FileNotFoundError:
        return


def is_gateway_healthy(url: str, timeout_seconds: float = 1.0) -> bool:
    """Check whether Kiro Gateway responds successfully.

    Args:
        url: Health endpoint URL.
        timeout_seconds: Per-request timeout.

    Returns:
        True when the endpoint returns a 2xx or 3xx status code.
    """

    try:
        with cast(
            HTTPResponse, urllib.request.urlopen(url, timeout=timeout_seconds)
        ) as response:
            status = response.status
            return 200 <= status < 400
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def wait_for_gateway(config: GatewayConfig) -> bool:
    """Wait until the gateway health endpoint is ready.

    Args:
        config: Gateway startup configuration.

    Returns:
        True when the gateway becomes healthy before timeout.
    """

    deadline = time.monotonic() + config.timeout_seconds
    while time.monotonic() <= deadline:
        if is_gateway_healthy(config.health_url):
            return True
        time.sleep(config.poll_interval_seconds)
    return False


def start_gateway(config: GatewayConfig) -> int:
    """Start Kiro Gateway as a detached background process.

    Args:
        config: Gateway startup configuration.

    Returns:
        Process id for the launched gateway.

    Raises:
        FileNotFoundError: If ``main.py`` is not present in the gateway dir.
        subprocess.SubprocessError: If the process cannot be launched.
    """

    main_file = config.gateway_dir / "main.py"
    if not main_file.exists():
        raise FileNotFoundError(f"main.py not found in {config.gateway_dir}")

    config.pid_file.parent.mkdir(parents=True, exist_ok=True)
    config.log_file.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"

    with config.log_file.open("ab") as log_handle:
        if os.name == "nt":
            process = subprocess.Popen(
                config.start_command,
                cwd=config.gateway_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
        else:
            process = subprocess.Popen(
                config.start_command,
                cwd=config.gateway_dir,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                start_new_session=True,
            )

    _ = config.pid_file.write_text(f"{process.pid}\n", encoding="utf-8")
    return process.pid


def ensure_gateway(config: GatewayConfig) -> str:
    """Ensure the gateway is healthy, starting it if needed.

    Args:
        config: Gateway startup configuration.

    Returns:
        A status string describing the action taken.

    Raises:
        RuntimeError: If the gateway does not become healthy after launch.
    """

    if is_gateway_healthy(config.health_url):
        return "already_running"

    existing_pid = read_pid_file(config.pid_file)
    if existing_pid is not None and not is_process_alive(existing_pid):
        remove_stale_pid_file(config.pid_file)
    elif existing_pid is not None:
        if wait_for_gateway(config):
            return f"already_starting:{existing_pid}"
        message = (
            f"Kiro Gateway process {existing_pid} exists but is not healthy at {config.health_url}. "
            + f"Check logs: {config.log_file}"
        )
        raise RuntimeError(message)

    if config.dry_run:
        print("Would start Kiro Gateway:", " ".join(config.start_command))
        return "would_start"

    pid = start_gateway(config)
    if wait_for_gateway(config):
        return f"started:{pid}"

    message = (
        f"Kiro Gateway process {pid} did not become healthy at {config.health_url}. "
        + f"Check logs: {config.log_file}"
    )
    raise RuntimeError(message)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments for the gateway launcher.

    Args:
        argv: Optional argument sequence. Defaults to ``sys.argv``.

    Returns:
        Parsed arguments.
    """

    repo_root = Path(__file__).resolve().parents[1]
    runtime_dir = repo_root / ".kiro-gateway"

    parser = argparse.ArgumentParser(
        description="Start Kiro Gateway in the background if it is not already running."
    )
    _ = parser.add_argument(
        "--gateway-dir",
        type=Path,
        default=repo_root,
        help="Kiro Gateway repository root containing main.py.",
    )
    _ = parser.add_argument(
        "--python",
        dest="python_executable",
        default=sys.executable,
        help="Python executable used to start the gateway.",
    )
    _ = parser.add_argument("--host", default=DEFAULT_HOST, help="Gateway host.")
    _ = parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Gateway port."
    )
    _ = parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help="Seconds to wait for the gateway health check.",
    )
    _ = parser.add_argument(
        "--poll-interval",
        type=float,
        default=DEFAULT_POLL_INTERVAL_SECONDS,
        help="Seconds between health check attempts.",
    )
    _ = parser.add_argument(
        "--health-path", default="/health", help="Gateway health path."
    )
    _ = parser.add_argument(
        "--pid-file",
        type=Path,
        default=runtime_dir / "gateway.pid",
        help="PID file path.",
    )
    _ = parser.add_argument(
        "--log-file",
        type=Path,
        default=runtime_dir / "gateway.log",
        help="Background gateway log path.",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be started without launching the gateway.",
    )
    _ = parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Optional command to run after the gateway is ready. Prefix with --.",
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> GatewayConfig:
    """Build a typed gateway config from parsed CLI arguments.

    Args:
        args: Parsed CLI arguments.

    Returns:
        GatewayConfig instance.
    """

    gateway_dir = cast(Path, args.gateway_dir)
    pid_file = cast(Path, args.pid_file)
    log_file = cast(Path, args.log_file)

    return GatewayConfig(
        gateway_dir=gateway_dir.resolve(),
        python_executable=cast(str, args.python_executable),
        host=cast(str, args.host),
        port=cast(int, args.port),
        timeout_seconds=cast(float, args.timeout),
        poll_interval_seconds=cast(float, args.poll_interval),
        health_path=cast(str, args.health_path),
        pid_file=pid_file.resolve(),
        log_file=log_file.resolve(),
        dry_run=cast(bool, args.dry_run),
    )


def normalize_command(command: Sequence[str]) -> list[str]:
    """Remove argparse's remainder separator from a command.

    Args:
        command: Command sequence captured by argparse.REMAINDER.

    Returns:
        Command without a leading ``--`` separator.
    """

    if command and command[0] == "--":
        return list(command[1:])
    return list(command)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the ensure-gateway CLI.

    Args:
        argv: Optional argument sequence. Defaults to ``sys.argv``.

    Returns:
        Process exit code.
    """

    args = parse_args(argv)
    config = build_config(args)
    status = ensure_gateway(config)
    print(f"Kiro Gateway: {status}")

    command = normalize_command(cast(Sequence[str], args.command))
    if not command:
        return 0

    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
