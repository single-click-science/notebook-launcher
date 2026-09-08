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
JUPYTER_PORT = 8888  # host-side port; bound to 127.0.0.1 only

if getattr(sys, "frozen", False):
    REPO_PATH = Path(sys.executable).parent.resolve()
else:
    REPO_PATH = Path(__file__).parent.resolve()


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


def remove_stale_container():
    """Remove a leftover container from a previous run, if any."""
    print("🧹 Cleaning up any previous container...")
    subprocess.run(f"docker rm -f {CONTAINER_NAME}", shell=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def pull_image():
    """Pull the image so first-run and update latency happen up front, with clear output."""
    run(f"docker pull {IMAGE}")


def start_container():
    """Start the notebook image, bound to localhost only."""
    run(
        f"docker run -d --name {CONTAINER_NAME} "
        f"-p 127.0.0.1:{JUPYTER_PORT}:8888 {IMAGE}"
    )
    print("✅ Container started")


def wait_for_jupyter(timeout=60):
    """Wait until Jupyter is listening on the host port."""
    print(f"⏳ Waiting for Jupyter on port {JUPYTER_PORT}...")
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", JUPYTER_PORT)) == 0:
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


def open_jupyter(token):
    """Open JupyterLab in the browser."""
    if token:
        url = f"http://127.0.0.1:{JUPYTER_PORT}/lab?token={token}"
    else:
        # Fall back to the bare URL; user will need to copy the token
        # themselves from `docker logs`, e.g. `docker logs {CONTAINER_NAME}`.
        url = f"http://127.0.0.1:{JUPYTER_PORT}/lab"
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
    start_container()

    if wait_for_jupyter():
        token = get_jupyter_token()
        open_jupyter(token)
    else:
        print("❌ Jupyter never became reachable. Check `docker logs "
              f"{CONTAINER_NAME}` for details.")

    print("\n🎉 All set! Jupyter should be running.")
    input("Press Enter to exit...")


if __name__ == "__main__":
    main()
