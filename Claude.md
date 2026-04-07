# Claude Code Instructions — L2A CDU System

## Coding Conventions

- All source code must be written in English (variable names, function names, class names, file names)
- All code comments must be written in English
- This applies to all languages used in this project (Python, JavaScript/Svelte, etc.)

## Project Overview

L2A CDU system running on Raspberry Pi 4. See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design.

Key components:
- **MCG** (Modbus Control Gateway): Modbus RTU master, central control hub — see [docs/MCG.md](docs/MCG.md)
- **PCB** (Modbus Slave): OP_MODE / Watchdog / Flash 파라미터 기반 자율 동작 — see [docs/PCB.md](docs/PCB.md)
- **UI** (Local + Web): PySide6 / Svelte + FastAPI — see [docs/UI.md](docs/UI.md)
- **UI Design**: Layout wireframes (Local + Web, Monitoring + History) — see [docs/UI_Design.md](docs/UI_Design.md)
- **Kiosk**: Kiosk mode configuration — see [docs/Kiosk.md](docs/Kiosk.md)

> **Doc rule**: Key components lists only items that have a corresponding file under `docs/`. When a new `docs/*.md` is created, add it here.

## Development Order

> **Code rule**: All source code must be written **after all `docs/*.md` files are finalized**. Do not write implementation code while documentation is still in progress.

## Project Structure

```
src/
├── local_ui/        # PySide6 app (FE+BE combined)
└── web_ui/
    ├── backend/     # FastAPI
    └── frontend/    # Svelte + Vite
docs/
├── MCG.md
├── PCB.md
├── UI.md
├── UI_Design.md
└── Kiosk.md
```
