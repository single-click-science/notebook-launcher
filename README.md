# single-click-dandi

A one-click desktop app that runs DANDI example notebooks inside a prebuilt Docker environment. It pulls a notebook image from the [DANDI Archive example-notebooks](https://github.com/dandi/example-notebooks) registry, starts JupyterLab locally, and opens it in your browser — no Python, conda, or CLI setup required.

This launcher is part of the [Single Click Science](https://github.com/single-click-science) project, which provides portable, reproducible execution environments for computational neuroscience. The launcher integrates with DANDI but remains an independent, ecosystem-neutral tool.

## Current Release

This version launches the [DANDI:001550](https://dandiarchive.org/dandiset/001550) notebooks (Pagan Lab behavioral and optogenetics demos) using a fixed, prebuilt image. Future releases will automatically select the correct image from DANDI's GitHub workflows.

## Download

Docker must be running. You can install Docker Desktop here: https://www.docker.com/products/docker-desktop/

Download the zip for your operating system from the [Latest Release](https://github.com/single-click-science/single-click-dandi/releases/latest) page and extract it.

- [Windows](https://github.com/single-click-science/single-click-dandi/releases/latest/download/single-click-dandi-windows.zip)
- [macOS](https://github.com/single-click-science/single-click-dandi/releases/latest/download/single-click-dandi-macos.zip)
- [Linux](https://github.com/single-click-science/single-click-dandi/releases/latest/download/single-click-dandi-linux.zip)

Do not use "Code → Download ZIP." That downloads only the source code, not the launcher.

## How to Run

1. Start Docker.
2. Open the extracted folder.
3. Double-click the launcher.

On first run, the launcher will:

- pull the notebook image (later runs only fetch updates)
- copy the notebooks into a `work/` folder next to the launcher
- start JupyterLab on a free local port (8888 or the next available)
- open JupyterLab in your browser with a fresh random access token

Your edits are saved in the `work/` folder and persist across runs. When finished, press Enter in the launcher window or close it — the Docker container will stop and clean up automatically.

## Security & Permissions

These binaries are not code-signed or notarized yet, so your OS will warn you on first launch.

- **Windows:** SmartScreen may show "Windows protected your PC." Choose **More info → Run anyway**. Some antivirus tools may quarantine PyInstaller executables; restore or whitelist if needed.
- **macOS:** Right-click (or Control-click) the launcher and choose **Open**, then confirm. This is only required once.
- **Linux:** If double-clicking does nothing, ensure the file is executable: `chmod +x launch`. Or enable "Allow executing file as program" in the file's Properties.

If the launcher opens as text, the executable bit is missing — apply the fix above.

## Attribution

The notebooks are from the [DANDI example-notebooks](https://github.com/dandi/example-notebooks) repository. The DANDI:001550 dataset accompanies:

> Pagan, M. et al. Individual variability of neural computations underlying flexible decisions. *Nature* 639, 421–429 (2025). [https://doi.org/10.1038/s41586-024-08433-6](https://doi.org/10.1038/s41586-024-08433-6)

## License & Contribution

The launcher is part of the Single Click Science project and is maintained independently of DANDI. Integration code is open-source ([MIT License](LICENSE)) and may be used by DANDI Archive or other archives. The core SCS engine remains a separate project with its own roadmap and governance.
