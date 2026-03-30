# Claude Code Instructions — L2A CDU System

## Coding Conventions

- All source code must be written in English (variable names, function names, class names, file names)
- All code comments must be written in English
- This applies to all languages used in this project (Python, JavaScript/Svelte, etc.)

## Project Overview

L2A CDU system running on Raspberry Pi 4. See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design.

Key components:
- **PCG** (Python Control Gateway): Modbus RTU master, central control hub — see [docs/PCG.md](docs/PCG.md)
- **Local UI**: PySide6, communicates with PCG via Unix Domain Socket IPC
- **Web UI**: Svelte (FE) + FastAPI (BE), communicates with PCG via REST API
- **DB**: Redis (real-time), Prometheus (history via exporter)

## Project Structure

```
src/
├── local_ui/        # PySide6 app (FE+BE combined)
└── web_ui/
    ├── backend/     # FastAPI
    └── frontend/    # Svelte + Vite
docs/
├── PCG.md
├── UI.md
└── Kiosk.md
```
