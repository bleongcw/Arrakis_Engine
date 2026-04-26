"""Tests for src/dev_runner.py — v1.5.0 serve command helper.

Exercises the orchestration logic in isolation: pre-flight checks,
subprocess argv building, output prefixing + ready-line detection,
process-group teardown.
"""
from __future__ import annotations

import io
import signal
import subprocess
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from src.dev_runner import (
    DevRunnerError,
    NEXTJS_READY_PATTERN,
    check_node_modules,
    find_pnpm,
    print_unified_banner,
    spawn_frontend,
    tail_with_prefix,
    terminate_process_group,
    wait_for_ready,
)


# ── find_pnpm ─────────────────────────────────────────────────────────────


class TestFindPnpm:
    @patch("src.dev_runner.shutil.which")
    def test_direct_pnpm_preferred(self, mock_which):
        mock_which.return_value = "/usr/local/bin/pnpm"
        assert find_pnpm() == ["/usr/local/bin/pnpm"]

    @patch("src.dev_runner.subprocess.run")
    @patch("src.dev_runner.shutil.which")
    def test_falls_back_to_corepack(self, mock_which, mock_run):
        # Direct pnpm missing, corepack present, corepack pnpm --version works
        mock_which.side_effect = lambda name: (
            "/usr/local/bin/corepack" if name == "corepack" else None
        )
        mock_run.return_value = MagicMock(returncode=0)
        result = find_pnpm()
        assert result == ["/usr/local/bin/corepack", "pnpm"]

    @patch("src.dev_runner.shutil.which")
    def test_neither_available_raises(self, mock_which):
        mock_which.return_value = None
        with pytest.raises(DevRunnerError, match="pnpm not found"):
            find_pnpm()

    @patch("src.dev_runner.subprocess.run")
    @patch("src.dev_runner.shutil.which")
    def test_corepack_present_but_pnpm_failed(self, mock_which, mock_run):
        """If corepack exists but `corepack pnpm --version` fails (network,
        missing pnpm package), we should still raise the clear error."""
        mock_which.side_effect = lambda name: (
            "/usr/local/bin/corepack" if name == "corepack" else None
        )
        mock_run.side_effect = subprocess.CalledProcessError(1, "corepack")
        with pytest.raises(DevRunnerError, match="pnpm not found"):
            find_pnpm()


# ── check_node_modules ───────────────────────────────────────────────────


class TestCheckNodeModules:
    def test_present(self, tmp_path):
        (tmp_path / "node_modules").mkdir()
        assert check_node_modules(tmp_path) is True

    def test_missing(self, tmp_path):
        assert check_node_modules(tmp_path) is False

    def test_file_not_dir(self, tmp_path):
        # node_modules exists as a file (weird, but defensive)
        (tmp_path / "node_modules").write_text("not a dir")
        assert check_node_modules(tmp_path) is False


# ── spawn_frontend ───────────────────────────────────────────────────────


class TestSpawnFrontend:
    @patch("src.dev_runner.subprocess.Popen")
    def test_basic_argv(self, mock_popen):
        spawn_frontend(["pnpm"], "frontend")
        args, kwargs = mock_popen.call_args
        assert args[0] == ["pnpm", "dev"]
        assert kwargs["cwd"] == "frontend"
        assert kwargs["stdout"] == subprocess.PIPE
        assert kwargs["stderr"] == subprocess.STDOUT
        assert kwargs["text"] is True

    @patch("src.dev_runner.subprocess.Popen")
    def test_with_explicit_port(self, mock_popen):
        spawn_frontend(["pnpm"], "frontend", port=3001)
        args, _kwargs = mock_popen.call_args
        # Next.js port forwarding goes through the `--` separator
        assert args[0] == ["pnpm", "dev", "--", "--port", "3001"]

    @patch("src.dev_runner.subprocess.Popen")
    def test_corepack_pnpm_argv(self, mock_popen):
        spawn_frontend(["corepack", "pnpm"], "frontend")
        args, _kwargs = mock_popen.call_args
        assert args[0] == ["corepack", "pnpm", "dev"]

    @patch("src.dev_runner.os.name", "posix")
    @patch("src.dev_runner.subprocess.Popen")
    def test_posix_uses_start_new_session(self, mock_popen):
        spawn_frontend(["pnpm"], "frontend")
        _, kwargs = mock_popen.call_args
        assert kwargs.get("start_new_session") is True


# ── tail_with_prefix ─────────────────────────────────────────────────────


class FakeProc:
    """Minimal Popen stand-in for tail_with_prefix tests."""
    def __init__(self, lines: list[str]):
        self.stdout = iter(lines)
        self._exit_code = None

    def poll(self):
        return self._exit_code

    def set_exited(self, code: int = 0):
        self._exit_code = code


class TestTailWithPrefix:
    def test_detects_nextjs_ready_line_legacy_format(self, capsys):
        proc = FakeProc(["▲ Next.js 16.2.1\n",
                         "- Local:    http://localhost:3000\n",
                         "- Ready in 1.2s\n"])
        ready = threading.Event()
        port_holder: dict = {}
        thread = tail_with_prefix(proc, "[fe]", ready, port_holder)
        thread.join(timeout=2)
        assert ready.is_set()
        assert port_holder.get("port") == 3000
        captured = capsys.readouterr()
        assert "[fe]" in captured.out

    def test_detects_port_bumped_to_3001(self, capsys):
        proc = FakeProc(["▲ Next.js 16.2.1\n",
                         "- Local:    http://localhost:3001\n"])
        ready = threading.Event()
        port_holder: dict = {}
        thread = tail_with_prefix(proc, "[fe]", ready, port_holder)
        thread.join(timeout=2)
        assert ready.is_set()
        assert port_holder.get("port") == 3001

    def test_eof_sets_event_so_waiters_dont_hang(self):
        """If the subprocess exits before printing a ready line, the tail
        thread should still set the event so wait_for_ready can return."""
        proc = FakeProc(["some unrelated output\n"])
        ready = threading.Event()
        thread = tail_with_prefix(proc, "[fe]", ready, {})
        thread.join(timeout=2)
        assert ready.is_set()

    def test_prefixes_each_line(self, capsys):
        proc = FakeProc(["compiling...\n", "ready\n",
                         "- Local:    http://localhost:3000\n"])
        ready = threading.Event()
        thread = tail_with_prefix(proc, "[frontend]", ready, {})
        thread.join(timeout=2)
        out = capsys.readouterr().out
        assert "[frontend] compiling..." in out
        assert "[frontend] ready" in out


class TestNextjsReadyPattern:
    @pytest.mark.parametrize("line,expected_port", [
        ("- Local:    http://localhost:3000", 3000),
        ("Local: http://localhost:3001", 3001),
        ("• Local:    http://localhost:8080", 8080),
        ("https://localhost:3000", 3000),
    ])
    def test_matches_known_formats(self, line, expected_port):
        m = NEXTJS_READY_PATTERN.search(line)
        assert m is not None
        assert int(m.group(1)) == expected_port

    @pytest.mark.parametrize("line", [
        "Compiling /...",
        "Module not found: foo.tsx",
        "Done in 2.3s",
    ])
    def test_does_not_match_unrelated_lines(self, line):
        m = NEXTJS_READY_PATTERN.search(line)
        assert m is None


# ── wait_for_ready ───────────────────────────────────────────────────────


class TestWaitForReady:
    def test_returns_true_when_event_set(self):
        proc = MagicMock()
        proc.poll.return_value = None  # alive
        event = threading.Event()
        event.set()
        assert wait_for_ready(event, proc, timeout_s=1.0) is True

    def test_returns_false_when_proc_dies(self):
        proc = MagicMock()
        # Alive on first poll, dead on second
        proc.poll.side_effect = [None, 1, 1, 1]
        proc.returncode = 1
        event = threading.Event()  # never set
        # wait_for_ready loops with sleep(0.1); 0.5s is plenty
        assert wait_for_ready(event, proc, timeout_s=2.0) is False

    def test_times_out(self):
        proc = MagicMock()
        proc.poll.return_value = None  # always alive
        event = threading.Event()
        start = time.monotonic()
        result = wait_for_ready(event, proc, timeout_s=0.3)
        elapsed = time.monotonic() - start
        assert result is False
        assert 0.2 <= elapsed <= 1.0


# ── terminate_process_group ──────────────────────────────────────────────


class TestTerminateProcessGroup:
    def test_already_dead_returns_immediately(self):
        proc = MagicMock()
        proc.poll.return_value = 0  # already exited
        # Should not call os.killpg or proc.wait
        with patch("src.dev_runner.os.killpg") as mock_killpg:
            terminate_process_group(proc)
            mock_killpg.assert_not_called()

    @patch("src.dev_runner.os.name", "posix")
    @patch("src.dev_runner.os.getpgid", return_value=12345)
    @patch("src.dev_runner.os.killpg")
    def test_graceful_sigterm_then_exit(self, mock_killpg, mock_getpgid):
        proc = MagicMock()
        proc.pid = 99999
        proc.poll.return_value = None  # alive when we enter
        # wait() returns successfully (process exited within grace)
        proc.wait.return_value = 0
        terminate_process_group(proc, grace_s=1.0)
        # First killpg call is SIGTERM
        first_call = mock_killpg.call_args_list[0]
        assert first_call[0][0] == 12345
        assert first_call[0][1] == signal.SIGTERM
        # Only ONE killpg call — no SIGKILL needed
        assert mock_killpg.call_count == 1

    @patch("src.dev_runner.os.name", "posix")
    @patch("src.dev_runner.os.getpgid", return_value=12345)
    @patch("src.dev_runner.os.killpg")
    def test_sigkill_after_grace_period(self, mock_killpg, mock_getpgid):
        proc = MagicMock()
        proc.pid = 99999
        proc.poll.return_value = None
        # wait() raises TimeoutExpired — process didn't die after SIGTERM
        proc.wait.side_effect = subprocess.TimeoutExpired(cmd="x", timeout=1)
        terminate_process_group(proc, grace_s=0.1)
        # Two killpg calls: SIGTERM then SIGKILL
        assert mock_killpg.call_count == 2
        signals = [call[0][1] for call in mock_killpg.call_args_list]
        assert signals == [signal.SIGTERM, signal.SIGKILL]


# ── print_unified_banner ─────────────────────────────────────────────────


class TestPrintUnifiedBanner:
    def test_includes_both_urls(self):
        out = io.StringIO()
        print_unified_banner(
            api_port=8000,
            frontend_port=3001,
            db_path="data/test.db",
            sched_status="enabled",
            interval_hours=6,
            out=out,
        )
        text = out.getvalue()
        assert "http://localhost:3001" in text
        assert "http://localhost:8000" in text
        assert "data/test.db" in text
        assert "enabled" in text
        assert "Press Ctrl+C" in text

    def test_marks_frontend_as_open_this(self):
        out = io.StringIO()
        print_unified_banner(8000, 3000, "x.db", "disabled", 6, out=out)
        # The frontend line should have the "open this" pointer because
        # that's the URL the user actually visits
        text = out.getvalue()
        frontend_line = next(
            (line for line in text.splitlines() if "3000" in line),
            "",
        )
        assert "open this" in frontend_line.lower() or "←" in frontend_line
