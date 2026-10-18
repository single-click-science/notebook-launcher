import sys
import subprocess
import socket
import time
import itertools
import threading
import webbrowser
import atexit
import secrets
import signal
from pathlib import Path

# ----------------- Config -----------------

# Placeholder: which prebuilt notebook image to run. This will eventually be
# supplied by the DANDI example-notebooks GitHub workflow rather than
# hard-coded here.
IMAGE = "ghcr.io/dandi/example-notebooks/001550-paganlab:latest"

CONTAINER_NAME = "dandi-example-notebook"
DEFAULT_PORT = 8888  # preferred host-side port; bound to 127.0.0.1 only

if getattr(sys, "frozen", False):
    REPO_PATH = Path(sys.executable).parent.resolve()
else:
    REPO_PATH = Path(__file__).parent.resolve()

# Host folder where notebooks persist across runs. Bind-mounted over /work
# in the container, so edits and outputs land here instead of being lost
# when the container is removed.
WORK_DIR = REPO_PATH / "work"
CONTAINER_WORK_PATH = "/work"

# Generated fresh on every launch so each user's Jupyter server has its own
# random secret. Passed into the container as JUPYTER_TOKEN, which Jupyter
# Server uses instead of generating its own.
JUPYTER_TOKEN = secrets.token_hex(24)


# ----------------- Progress indicator -----------------

class Spinner:
    """
    Simple console spinner for indeterminate waits. Use as a context manager
    around any blocking call:

        with Spinner("Checking Docker..."):
            subprocess.run("docker info", shell=True, check=True)

    ASCII-only spin characters (no emoji) so it renders cleanly when
    overwritten in place on Windows' default console codepage.
    """

    def __init__(self, message="Working...", interval=0.1):
        self.message = message
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread = None

    def _spin(self):
        frames = itertools.cycle(["|", "/", "-", "\\"])
        start = time.time()
        while not self._stop_event.is_set():
            elapsed = int(time.time() - start)
            sys.stdout.write(f"\r{self.message} {next(frames)} ({elapsed}s)")
            sys.stdout.flush()
            time.sleep(self.interval)
        # Clear the line when done
        sys.stdout.write("\r" + " " * (len(self.message) + 15) + "\r")
        sys.stdout.flush()

    def start(self):
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


# ----------------- Helpers -----------------

def run(command, **kwargs):
    """Run a command from project root and exit on failure."""
    print(f"Running: {command}")
    try:
        return subprocess.run(
            command,
            shell=True,
            check=True,
            cwd=REPO_PATH,
            **kwargs,
        )
    except subprocess.CalledProcessError:
        print(f"❌ Command failed: {command}")
        input("Press Enter to exit...")
        sys.exit(1)


def check_docker():
    """Check if Docker is running."""
    with Spinner("Checking Docker..."):
        try:
            subprocess.run(
                "docker info",
                shell=True,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            ok = True
        except subprocess.CalledProcessError:
            ok = False

    if ok:
        print("✅ Docker is running")
    else:
        print("❌ Docker is not running. Please start Docker Desktop and try again.")
        input("Press Enter to exit...")
        sys.exit(1)


def find_free_port(start_port=DEFAULT_PORT, max_tries=20):
    """
    Find a port on 127.0.0.1 that's actually free, starting at start_port and
    counting up. This is what lets the launcher work even when something else
    on the machine (another app, another Jupyter server) already holds the
    default port — no manual cleanup required from the user.
    """
    port = start_port
    for _ in range(max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return port
            except OSError:
                port += 1
    return None


def remove_stale_container():
    """Remove a leftover container from a previous run, if any."""
    print("🧹 Cleaning up any previous container...")
    subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pull_image():
    """
    Pull the image so first-run and update latency happen up front.
    Deliberately NOT wrapped in Spinner: `docker pull` already streams its
    own real layer-by-layer download progress when left uncaptured, which is
    more informative than a generic spinner — capturing it to drive a
    spinner would throw that away.
    """
    run(f"docker pull {IMAGE}")


def seed_work_dir():
    """
    On first run, copy the notebooks out of the image into WORK_DIR on disk.
    Must happen before WORK_DIR is ever bind-mounted over /work — mounting an
    empty host folder there would hide the image's notebooks instead of
    preserving them. Skipped on later runs once WORK_DIR already has content.
    """
    if WORK_DIR.exists() and any(WORK_DIR.iterdir()):
        return  # already seeded from a previous run

    print(f"📁 Setting up local notebook folder at {WORK_DIR} (first run)...")
    WORK_DIR.mkdir(parents=True, exist_ok=True)

    seed_name = f"{CONTAINER_NAME}-seed"
    subprocess.run(f"docker rm -f {seed_name}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # `docker create` makes the container without starting it — enough to
    # copy files out of its filesystem via `docker cp`.
    run(f"docker create --name {seed_name} {IMAGE}")
    run(f'docker cp {seed_name}:{CONTAINER_WORK_PATH}/. "{WORK_DIR}"')
    subprocess.run(f"docker rm -f {seed_name}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # The image's /work also holds setup files (README, environment.yml,
    # requirements.in) for people building the environment by hand. The
    # image already provides that environment, so keep only the notebooks
    # to avoid confusing users. Subfolders are left alone in case a
    # notebook reads data from them.
    for path in WORK_DIR.iterdir():
        if path.is_file() and path.suffix != ".ipynb":
            path.unlink()

    print(f"✅ Notebooks copied to {WORK_DIR}")


_shutdown_done = False


def stop_container():
    """Stop and remove the notebook container. Safe to call more than once.
    Notebooks live in the bind-mounted WORK_DIR, so removing the container
    doesn't lose saved work."""
    global _shutdown_done
    if _shutdown_done:
        return
    _shutdown_done = True
    print("\n🛑 Stopping Docker container...")
    subprocess.run(f"docker stop --time 5 {CONTAINER_NAME}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _handle_termination_signal(signum, frame):
    stop_container()
    sys.exit(0)


def _register_shutdown_handlers():
    """Make sure the container stops no matter how the launcher closes:
    pressing Enter, Ctrl+C, or the console window being closed/logged
    off/shut down (Windows doesn't run atexit handlers for that last case,
    so it needs its own console control handler)."""
    atexit.register(stop_container)

    for sig_name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
        sig = getattr(signal, sig_name, None)
        if sig is not None:
            try:
                signal.signal(sig, _handle_termination_signal)
            except (ValueError, OSError):
                pass

    if sys.platform == "win32":
        import ctypes

        # Event types: 0=CTRL_C, 1=CTRL_BREAK, 2=CTRL_CLOSE, 5=CTRL_LOGOFF, 6=CTRL_SHUTDOWN
        handler_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_uint)

        def _console_ctrl_handler(ctrl_type):
            stop_container()
            return False

        # Keep a reference so it isn't garbage-collected before Windows calls it.
        global _console_ctrl_handler_ref
        _console_ctrl_handler_ref = handler_type(_console_ctrl_handler)
        ctypes.windll.kernel32.SetConsoleCtrlHandler(_console_ctrl_handler_ref, True)


def start_container(starting_port, max_tries=20):
    """
    Start the notebook image, bound to localhost only. If Docker reports the
    port as already allocated, remove the failed container and retry on the
    next port, rather than trusting a pre-flight check alone — Docker Desktop
    tracks port reservations internally, so a port can look free to a plain
    socket test and still be rejected by the daemon (as happened here).
    Returns the port that actually worked.
    """
    port = starting_port
    for attempt in range(max_tries):
        command = (
            f"docker run -d --name {CONTAINER_NAME} "
            f"-p 127.0.0.1:{port}:8888 "
            f"-e JUPYTER_TOKEN={JUPYTER_TOKEN} "
            f'-v "{WORK_DIR}:{CONTAINER_WORK_PATH}" '
            f"{IMAGE}"
        )
        print(f"Running: {command}")
        result = subprocess.run(
            command, shell=True, cwd=REPO_PATH, capture_output=True, text=True
        )

        if result.returncode == 0:
            print(f"✅ Container started on port {port}")
            return port

        stderr = result.stderr or ""
        if "port is already allocated" in stderr or "address already in use" in stderr.lower():
            print(f"⚠️ Port {port} is already in use, trying {port + 1}...")
            # `docker run -d` can create the container before the network
            # setup step fails, leaving a dead container holding our name —
            # remove it before the retry or the next attempt fails on a name
            # conflict instead of a port conflict.
            subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            port += 1
            continue

        print(f"❌ Command failed: {command}\n{stderr}")
        input("Press Enter to exit...")
        sys.exit(1)

    print("❌ Couldn't find a free port after several attempts.")
    input("Press Enter to exit...")
    sys.exit(1)


def wait_for_jupyter(port, timeout=60):
    """Wait until Jupyter is listening on the host port."""
    ready = False
    with Spinner(f"Waiting for Jupyter on port {port}..."):
        start = time.time()
        while time.time() - start < timeout:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                if sock.connect_ex(("127.0.0.1", port)) == 0:
                    ready = True
                    break
            time.sleep(1)

    if ready:
        print("✅ Jupyter is ready")
    else:
        print("⚠️ Timeout waiting for Jupyter")
    return ready


def open_jupyter(port):
    """Open JupyterLab in the browser."""
    url = f"http://127.0.0.1:{port}/lab?token={JUPYTER_TOKEN}"
    print(f"🌐 Opening Jupyter at: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        print(f"Visit manually:\n{url}")


# ----------------- Main -----------------

def main():
    print("📦 Starting DANDI example notebook\n" + "=" * 40)

    _register_shutdown_handlers()

    check_docker()
    remove_stale_container()
    pull_image()
    seed_work_dir()

    starting_guess = find_free_port()
    if starting_guess is None:
        starting_guess = DEFAULT_PORT  # let start_container's own retry loop sort it out

    try:
        port = start_container(starting_guess)
        if port != DEFAULT_PORT:
            print(f"ℹ️ Port {DEFAULT_PORT} was busy, using {port} instead.")

        if wait_for_jupyter(port):
            open_jupyter(port)
        else:
            print("❌ Jupyter never became reachable. Check `docker logs "
                  f"{CONTAINER_NAME}` for details.")

        print(f"\n🎉 All set! Jupyter should be running. Your notebooks are saved in:\n{WORK_DIR}")
        input("Press Enter to stop Jupyter and exit...")
    finally:
        stop_container()


if __name__ == "__main__":
    main()
