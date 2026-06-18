from __future__ import annotations

import fcntl
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

PORT = int(os.environ.get("PORT", "7860"))
VLLM_PORT = int(os.environ.get("VLLM_PORT", "8000"))
FASTAPI_PORT = int(os.environ.get("FASTAPI_PORT", "8010"))
STREAMLIT_PORT = int(os.environ.get("STREAMLIT_PORT", "8501"))
VLLM_MODEL = os.environ.get("VLLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-4B-BF16")


def _listener_inodes(port: int) -> set[str]:
    target_port = f"{port:04X}"
    inodes: set[str] = set()
    for table_path in ("/proc/net/tcp", "/proc/net/tcp6"):
        table = Path(table_path)
        if not table.exists():
            continue
        lines = table.read_text(encoding="utf-8").splitlines()[1:]
        for line in lines:
            columns = line.split()
            if len(columns) < 10:
                continue
            local_address = columns[1]
            state = columns[3]
            inode = columns[9]
            _, port_hex = local_address.rsplit(":", 1)
            if state == "0A" and port_hex == target_port:
                inodes.add(inode)
    return inodes


def _pid_command(pid: int) -> str:
    try:
        raw = Path(f"/proc/{pid}/cmdline").read_bytes()
    except OSError:
        return ""
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _listener_pids(port: int) -> list[int]:
    inodes = _listener_inodes(port)
    if not inodes:
        return []
    pids: list[int] = []
    for proc_dir in Path("/proc").iterdir():
        if not proc_dir.name.isdigit():
            continue
        fd_dir = proc_dir / "fd"
        try:
            fds = list(fd_dir.iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(fd)
            except OSError:
                continue
            if target.startswith("socket:[") and target[8:-1] in inodes:
                pids.append(int(proc_dir.name))
                break
    return sorted(set(pids))


def _acquire_startup_lock(lock_path: str = "/tmp/catcon_space_repo_start.lock") -> object:
    lock_file = Path(lock_path).open("w")
    fcntl.flock(lock_file, fcntl.LOCK_EX)
    os.set_inheritable(lock_file.fileno(), True)
    return lock_file


def _can_bind_port(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            probe.bind(("0.0.0.0", port))
        except OSError:
            return False
    return True


def _wait_for_port_release(port: int, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    last_reported: tuple[int, ...] | None = None
    while True:
        listeners = [pid for pid in _listener_pids(port) if pid not in {os.getpid(), os.getppid()}]
        if not listeners and _can_bind_port(port):
            return
        listener_signature = tuple(listeners)
        if listener_signature != last_reported:
            if listeners:
                print(f"Port {port} is already in use; waiting for listener(s) to exit: {listeners}", flush=True)
                for pid in listeners:
                    print(f" - pid {pid}: {_pid_command(pid)}", flush=True)
            else:
                print(f"Port {port} is still not bindable; waiting", flush=True)
            last_reported = listener_signature
        if time.time() >= deadline:
            raise RuntimeError(f"Port {port} is still busy after {timeout:.0f}s")
        time.sleep(1.0)


def _wait_for_port_open(port: int, timeout: float = 120.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.0):
                return
        except OSError:
            time.sleep(0.5)
    raise RuntimeError(f"Port {port} did not open within {timeout:.0f}s")


def _start_vllm() -> subprocess.Popen:
    cmd = [
        "python3", "-m", "vllm.entrypoints.openai.api_server",
        "--model", VLLM_MODEL,
        "--trust-remote-code",
        "--max-model-len", "8192",
        "--tensor-parallel-size", "1",
        "--enable-auto-tool-choice",
        "--tool-call-parser", "qwen3_coder",
        "--gpu-memory-utilization", "0.70",
        "--port", str(VLLM_PORT),
        "--host", "127.0.0.1",
    ]
    print(f"Starting vLLM: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)


def _start_fastapi() -> subprocess.Popen:
    cmd = [
        "python3", "-m", "uvicorn",
        "disruptron.api:app",
        "--host", "127.0.0.1",
        "--port", str(FASTAPI_PORT),
    ]
    print(f"Starting FastAPI: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)


def _start_streamlit() -> subprocess.Popen:
    cmd = [
        "python3", "-m", "streamlit", "run", "app.py",
        f"--server.port={STREAMLIT_PORT}",
        "--server.address=127.0.0.1",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--server.runOnSave=false",
        "--browser.gatherUsageStats=false",
    ]
    print(f"Starting Streamlit: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)


def _start_proxy() -> subprocess.Popen:
    cmd = [
        "python3", "-m", "uvicorn",
        "disruptron.proxy:app",
        "--host", "0.0.0.0",
        "--port", str(PORT),
    ]
    print(f"Starting proxy: {' '.join(cmd)}", flush=True)
    return subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)


def _terminate_children(children: list[subprocess.Popen]) -> None:
    for child in children:
        try:
            child.send_signal(signal.SIGTERM)
        except Exception:
            pass
    for child in children:
        try:
            child.wait(timeout=5.0)
        except Exception:
            child.kill()


def main() -> None:
    os.environ.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")
    os.environ.setdefault("STREAMLIT_SERVER_FILE_WATCHER_TYPE", "none")
    os.environ.setdefault("STREAMLIT_SERVER_RUN_ON_SAVE", "false")

    _startup_lock = _acquire_startup_lock()
    _wait_for_port_release(PORT)

    processes: list[subprocess.Popen] = []
    try:
        processes.append(_start_vllm())
        print(f"Waiting for vLLM on port {VLLM_PORT}...", flush=True)
        _wait_for_port_open(VLLM_PORT, timeout=300.0)

        processes.append(_start_fastapi())
        print(f"Waiting for FastAPI on port {FASTAPI_PORT}...", flush=True)
        _wait_for_port_open(FASTAPI_PORT, timeout=60.0)

        processes.append(_start_streamlit())
        print(f"Waiting for Streamlit on port {STREAMLIT_PORT}...", flush=True)
        _wait_for_port_open(STREAMLIT_PORT, timeout=60.0)

        processes.append(_start_proxy())
        print(f"Waiting for proxy on port {PORT}...", flush=True)
        _wait_for_port_open(PORT, timeout=60.0)

        print("All services are running. Holding main process.", flush=True)
        while True:
            for p in processes:
                ret = p.poll()
                if ret is not None:
                    print(f"Child process exited with code {ret}; shutting down.", flush=True)
                    _terminate_children(processes)
                    sys.exit(1)
            time.sleep(1.0)
    except Exception as exc:
        print(f"Fatal error: {exc}", flush=True)
        _terminate_children(processes)
        raise


if __name__ == "__main__":
    main()
