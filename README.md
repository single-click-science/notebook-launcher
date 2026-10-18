# single-click-dandi

A one-click launcher for DANDI example notebooks. It pulls a prebuilt notebook image from the [DANDI example-notebooks](https://github.com/dandi/example-notebooks) registry, starts JupyterLab in Docker, and opens it in your browser — no Python or conda setup required.

The default image is [DANDI:001550](https://dandiarchive.org/dandiset/001550) (Pagan Lab behavioral and optogenetics notebooks). To launch a different notebook, change `IMAGE` at the top of `launch_mount_dandi_notebook.py`.

## Download

This app requires Docker running. Docker can be downloaded here: https://www.docker.com/products/docker-desktop/.
Download the zip for your OS from the [latest release](https://github.com/MarikeReimer/single-click-dandi/releases/latest), then extract it.

- [Windows](https://github.com/MarikeReimer/single-click-dandi/releases/latest/download/single-click-dandi-windows.zip)
- [macOS](https://github.com/MarikeReimer/single-click-dandi/releases/latest/download/single-click-dandi-macos.zip)
- [Linux](https://github.com/MarikeReimer/single-click-dandi/releases/latest/download/single-click-dandi-linux.zip)

Do not use the green "Code" → "Download ZIP" button on this repo — that downloads the source code only, without the built launcher.

## How to Run

1. Make sure Docker is running.
2. Open the extracted folder and double-click the launcher.

The launcher will:

- pull the notebook image (the first run downloads it; later runs only fetch updates)
- on first run, copy the notebooks into a `work/` folder next to the launcher
- start JupyterLab on a free local port (8888, or the next free one), reachable only from this machine, with a fresh random access token
- open JupyterLab in your browser

Your notebooks and any edits are saved in the `work/` folder, so they survive between runs. When you're done, press Enter in the launcher window (or just close it) — the Docker container is stopped and removed automatically.

### Running from source

With Python 3 installed:

```bash
python launch_mount_dandi_notebook.py
```

## Permissions & Security Warnings

None of these binaries are code-signed or notarized, so every OS will flag them as coming from an unidentified source on first launch. This is expected — here's how to get past it on each platform:

- **Windows:** SmartScreen will likely show "Windows protected your PC." Click **"More info"**, then **"Run anyway."** Some antivirus software may also flag or quarantine `launch.exe` — this is a common false positive for PyInstaller-built executables. If it gets quarantined, restore it (or add an exclusion) from your antivirus's quarantine list.
- **macOS:** Gatekeeper will block the first launch with "*launch* cannot be opened because the developer cannot be verified." Instead of double-clicking, **right-click (or Control-click) the launcher and choose "Open,"** then confirm "Open" in the dialog. This is only needed the first time.
- **Linux:** Some file managers extract zips without restoring the executable bit. If double-clicking does nothing, open a terminal in the extracted folder and run `chmod +x launch`, then try again — or check "Allow executing file as program" in the file's Properties/Permissions tab.
- **Any OS:** If the launcher opens as garbled text in an editor instead of running, the executable permission bit is missing — the `chmod +x launch` fix above applies there too.

## Building a release

Pushing a tag starting with `v` (e.g. `v0.1.0`) runs the GitHub Actions workflow in `.github/workflows/build.yml`, which builds the launcher for Windows, macOS, and Linux with PyInstaller and attaches the zips to a GitHub release.

## Attribution

The notebooks are from the [DANDI example-notebooks](https://github.com/dandi/example-notebooks) repository. The DANDI:001550 dataset accompanies:

> Pagan, M. et al. Individual variability of neural computations underlying flexible decisions. *Nature* 639, 421–429 (2025). [https://doi.org/10.1038/s41586-024-08433-6](https://doi.org/10.1038/s41586-024-08433-6)
