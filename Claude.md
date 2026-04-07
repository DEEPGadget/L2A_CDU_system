# Claude Code Instructions — L2A CDU System

## Coding Conventions

- All source code must be written in English (variable names, function names, class names, file names)
- All code comments must be written in English
- This applies to all languages used in this project (Python, JavaScript/Svelte, etc.)

## Project Overview

L2A CDU system running on Raspberry Pi 4. See [ARCHITECTURE.md](ARCHITECTURE.md) for full system design.

Key components:
- **MCG** (Modbus Control Gateway): Modbus RTU master, central control hub — see [docs/v1/MCG.md](docs/v1/MCG.md) (v1) / [docs/v2/MCG.md](docs/v2/MCG.md) (v2)
- **PCB** (Modbus Slave): v1=단순 R/W, v2=OP_MODE/Watchdog 자율 동작 — see [docs/v1/PCB.md](docs/v1/PCB.md) / [docs/v2/PCB.md](docs/v2/PCB.md)
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
├── v1/
│   ├── MCG.md      # MCG 단독 시퀀스 처리 버전
│   └── PCB.md      # 단순 R/W Slave
├── v2/
│   ├── MCG.md      # PCB Watchdog/OP_MODE 연동 버전
│   └── PCB.md      # 자율 동작 포함
├── UI.md
├── UI_Design.md
└── Kiosk.md
```
