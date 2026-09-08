import os
import sys
import re
import subprocess
import socket
import time
import webbrowser
from pathlib import Path

# ----------------- Config -----------------

# Which prebuilt notebook image to run. Change this to the notebook you want,
# e.g. "ghcr.io/dandi/example-notebooks/001550-paganlab:latest"
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
    try:
        subprocess.run(
            "docker info",
            shell=True,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print("✅ Docker is running")
    except subprocess.CalledProcessError:
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
    """Pull the image so first-run and update latency happen up front, with clear output."""
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

    print(f"✅ Notebooks copied to {WORK_DIR}")


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
    print(f"⏳ Waiting for Jupyter on port {port}...")
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                print("✅ Jupyter is ready")
                return True
        time.sleep(1)

    print("⚠️ Timeout waiting for Jupyter")
    return False


def get_jupyter_token(timeout=30):
    """
    Jupyter generates its own token at container startup and prints a URL
    containing it to stdout/stderr. Poll `docker logs` until that URL shows up
    and pull the token out of it.
    """
    print("🔑 Reading Jupyter token from container logs...")
    pattern = re.compile(r"token=([a-zA-Z0-9]+)")
    start = time.time()

    while time.time() - start < timeout:
        result = subprocess.run(
            f"docker logs {CONTAINER_NAME}",
            shell=True,
            capture_output=True,
            text=True,
        )
        combined = result.stdout + result.stderr
        match = pattern.search(combined)
        if match:
            token = match.group(1)
            print("✅ Token found")
            return token
        time.sleep(1)

    print("⚠️ Could not find a token in the container logs.")
    return None


def open_jupyter(token, port):
    """Open JupyterLab in the browser."""
    if token:
        url = f"http://127.0.0.1:{port}/lab?token={token}"
    else:
        # Fall back to the bare URL; user will need to copy the token
        # themselves from `docker logs`, e.g. `docker logs {CONTAINER_NAME}`.
        url = f"http://127.0.0.1:{port}/lab"
        print(f"⚠️ Opening without a token. If prompted, run: docker logs {CONTAINER_NAME}")

    print(f"🌐 Opening Jupyter at: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        print(f"Visit manually:\n{url}")


# ----------------- Main -----------------

def main():
    print("📦 Starting DANDI example notebook\n" + "=" * 40)

    check_docker()
    remove_stale_container()
    pull_image()
    seed_work_dir()

    starting_guess = find_free_port()
    if starting_guess is None:
        starting_guess = DEFAULT_PORT  # let start_container's own retry loop sort it out

    port = start_container(starting_guess)
    if port != DEFAULT_PORT:
        print(f"ℹ️ Port {DEFAULT_PORT} was busy, using {port} instead.")

    if wait_for_jupyter(port):
        token = get_jupyter_token()
        open_jupyter(token, port)
    else:
        print("❌ Jupyter never became reachable. Check `docker logs "
              f"{CONTAINER_NAME}` for details.")

    print(f"\n🎉 All set! Jupyter should be running. Your notebooks are saved in:\n{WORK_DIR}")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
