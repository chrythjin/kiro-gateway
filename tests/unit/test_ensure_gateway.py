# -*- coding: utf-8 -*-

"""
Unit tests for scripts.ensure_gateway.
"""

import argparse
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import pytest

from scripts.ensure_gateway import (
    GatewayConfig,
    build_config,
    ensure_gateway,
    is_gateway_healthy,
    normalize_command,
    read_pid_file,
    start_gateway,
)


@pytest.fixture
def gateway_config(tmp_path: Path) -> GatewayConfig:
    """
    What it does: Builds a launcher config pointed at a temporary gateway repo.
    Purpose: Keeps launcher tests isolated from the real working tree runtime files.
    """
    gateway_dir = tmp_path / "gateway"
    gateway_dir.mkdir()
    _ = (gateway_dir / "main.py").write_text("print('gateway')\n", encoding="utf-8")

    return GatewayConfig(
        gateway_dir=gateway_dir,
        python_executable="python-test",
        host="127.0.0.1",
        port=8010,
        timeout_seconds=0.1,
        poll_interval_seconds=0.01,
        health_path="/health",
        pid_file=tmp_path / "runtime" / "gateway.pid",
        log_file=tmp_path / "runtime" / "gateway.log",
    )


class TestEnsureGatewaySuccess:
    """Tests for successful launcher paths."""

    def test_existing_healthy_gateway_skips_process_start(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies a healthy gateway exits without launching a process.
        Purpose: Prevent duplicate gateway processes on every OpenCode startup.
        """
        print("Setup: Mocking health check as already healthy...")

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=True
        ), patch("scripts.ensure_gateway.start_gateway") as start_gateway_mock:
            status = ensure_gateway(gateway_config)

        print(f"Status: {status}")
        assert status == "already_running"
        start_gateway_mock.assert_not_called()

    def test_missing_gateway_starts_process_and_writes_pid(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies the launcher starts a detached process and writes its PID.
        Purpose: Ensure OpenCode wrappers can bootstrap the gateway before running.
        """
        print("Setup: Mocking Popen with a fake PID...")
        process = Mock()
        process.pid = 12345

        with patch(
            "scripts.ensure_gateway.subprocess.Popen", return_value=process
        ) as popen_mock:
            pid = start_gateway(gateway_config)

        print(f"PID: {pid}")
        assert pid == 12345
        assert gateway_config.pid_file.read_text(encoding="utf-8") == "12345\n"
        popen_mock.assert_called_once()
        kwargs = cast(dict[str, object], popen_mock.call_args.kwargs)
        assert kwargs["cwd"] == gateway_config.gateway_dir
        assert kwargs["stdin"] == subprocess.DEVNULL

    def test_stale_pid_file_is_removed_before_start(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies a dead PID does not block a new gateway launch.
        Purpose: Recover automatically after a crash or reboot leaves stale runtime state.
        """
        print("Setup: Creating stale PID file...")
        gateway_config.pid_file.parent.mkdir(parents=True)
        _ = gateway_config.pid_file.write_text("99999\n", encoding="utf-8")

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=False
        ), patch("scripts.ensure_gateway.is_process_alive", return_value=False), patch(
            "scripts.ensure_gateway.start_gateway", return_value=22222
        ), patch(
            "scripts.ensure_gateway.wait_for_gateway", return_value=True
        ):
            status = ensure_gateway(gateway_config)

        print(f"Status: {status}")
        assert status == "started:22222"

    def test_live_pid_waits_instead_of_starting_duplicate(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies a live PID waits for health instead of launching again.
        Purpose: Prevent duplicate gateways when startup is already in progress.
        """
        print("Setup: Creating live PID file...")
        gateway_config.pid_file.parent.mkdir(parents=True)
        _ = gateway_config.pid_file.write_text("33333\n", encoding="utf-8")

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=False
        ), patch("scripts.ensure_gateway.is_process_alive", return_value=True), patch(
            "scripts.ensure_gateway.wait_for_gateway", return_value=True
        ), patch(
            "scripts.ensure_gateway.start_gateway"
        ) as start_gateway_mock:
            status = ensure_gateway(gateway_config)

        print(f"Status: {status}")
        assert status == "already_starting:33333"
        start_gateway_mock.assert_not_called()

    def test_dry_run_prints_command_without_starting(
        self, gateway_config: GatewayConfig, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """
        What it does: Verifies dry-run reports the launch command without side effects.
        Purpose: Let users validate OpenCode wrapper setup without starting services.
        """
        print("Setup: Enabling dry run...")
        dry_run_config = replace(gateway_config, dry_run=True)

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=False
        ), patch("scripts.ensure_gateway.start_gateway") as start_gateway_mock:
            status = ensure_gateway(dry_run_config)

        captured = capsys.readouterr()
        assert status == "would_start"
        assert "Would start Kiro Gateway" in captured.out
        start_gateway_mock.assert_not_called()


class TestEnsureGatewayErrors:
    """Tests for launcher error paths."""

    def test_live_pid_without_health_raises_actionable_error(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies a live but unhealthy PID fails without duplication.
        Purpose: Surface the existing log file instead of hiding a broken startup.
        """
        print("Setup: Creating live unhealthy PID file...")
        gateway_config.pid_file.parent.mkdir(parents=True)
        _ = gateway_config.pid_file.write_text("44444\n", encoding="utf-8")

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=False
        ), patch("scripts.ensure_gateway.is_process_alive", return_value=True), patch(
            "scripts.ensure_gateway.wait_for_gateway", return_value=False
        ), pytest.raises(
            RuntimeError, match="exists but is not healthy"
        ):
            _ = ensure_gateway(gateway_config)

    def test_started_gateway_timeout_raises_actionable_error(
        self, gateway_config: GatewayConfig
    ) -> None:
        """
        What it does: Verifies startup timeout includes health URL and log file context.
        Purpose: Help users troubleshoot failed background startup from OpenCode.
        """
        print("Setup: Mocking startup timeout...")

        with patch(
            "scripts.ensure_gateway.is_gateway_healthy", return_value=False
        ), patch("scripts.ensure_gateway.start_gateway", return_value=55555), patch(
            "scripts.ensure_gateway.wait_for_gateway", return_value=False
        ), pytest.raises(
            RuntimeError, match="did not become healthy"
        ):
            _ = ensure_gateway(gateway_config)

    def test_missing_main_file_raises_file_not_found(self, tmp_path: Path) -> None:
        """
        What it does: Verifies startup fails when the gateway directory is invalid.
        Purpose: Catch misconfigured wrapper paths before spawning an empty process.
        """
        print("Setup: Building config without main.py...")
        config = GatewayConfig(
            gateway_dir=tmp_path,
            python_executable="python-test",
            host="127.0.0.1",
            port=8010,
            timeout_seconds=0.1,
            poll_interval_seconds=0.01,
            health_path="/health",
            pid_file=tmp_path / "gateway.pid",
            log_file=tmp_path / "gateway.log",
        )

        with pytest.raises(FileNotFoundError, match="main.py not found"):
            _ = start_gateway(config)


class TestEnsureGatewayHelpers:
    """Tests for pure helper behavior."""

    def test_read_pid_file_returns_none_for_missing_or_malformed_files(
        self, tmp_path: Path
    ) -> None:
        """
        What it does: Verifies PID parsing tolerates missing and malformed files.
        Purpose: Avoid crashing OpenCode startup because of stale runtime files.
        """
        print("Setup: Testing missing PID file...")
        pid_file = tmp_path / "gateway.pid"
        assert read_pid_file(pid_file) is None

        print("Setup: Testing malformed PID file...")
        _ = pid_file.write_text("not-a-pid\n", encoding="utf-8")
        assert read_pid_file(pid_file) is None

    def test_health_check_returns_false_for_url_errors(self) -> None:
        """
        What it does: Verifies failed health requests are treated as not healthy.
        Purpose: Drive the launcher into the startup path without leaking exceptions.
        """
        print("Setup: Mocking urlopen failure...")

        with patch(
            "scripts.ensure_gateway.urllib.request.urlopen", side_effect=OSError("down")
        ):
            assert is_gateway_healthy("http://127.0.0.1:8000/health") is False

    def test_normalize_command_removes_argparse_separator(self) -> None:
        """
        What it does: Verifies the optional child command removes a leading -- separator.
        Purpose: Allow `ensure_gateway.py -- opencode` wrapper syntax.
        """
        print("Action: Normalizing commands...")
        assert normalize_command(["--", "opencode", "run"]) == ["opencode", "run"]
        assert normalize_command(["opencode", "run"]) == ["opencode", "run"]

    def test_build_config_uses_resolved_paths(self, tmp_path: Path) -> None:
        """
        What it does: Verifies parsed arguments become a typed launcher config.
        Purpose: Ensure CLI inputs map to the process launcher exactly.
        """
        print("Setup: Creating parsed args...")
        args = argparse.Namespace(
            gateway_dir=tmp_path,
            python_executable="python-test",
            host="127.0.0.1",
            port=9000,
            timeout=3.0,
            poll_interval=0.2,
            health_path="/health",
            pid_file=tmp_path / "pid.txt",
            log_file=tmp_path / "gateway.log",
            dry_run=True,
        )

        config = build_config(args)

        assert config.gateway_dir == tmp_path.resolve()
        assert config.pid_file == (tmp_path / "pid.txt").resolve()
        assert config.health_url == "http://127.0.0.1:9000/health"
