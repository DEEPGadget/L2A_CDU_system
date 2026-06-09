# L2A CDU System

Raspberry Pi 4 기반 냉각수 분배 장치(CDU) 제어 시스템.
Modbus RTU로 PCB와 통신하며, 터치 디스플레이 및 웹 브라우저를 통해 모니터링·제어를 제공한다.

시스템 전체 구성은 [ARCHITECTURE.md](ARCHITECTURE.md) 참고.

## 구성 요소

| 컴포넌트 | 설명 |
|---|---|
| MCG | Modbus Control Gateway — Modbus RTU Master, 중앙 제어 허브 |
| Local UI | PySide6 기반 터치 디스플레이 UI |
| Web UI | Svelte (FE) + FastAPI (BE) 기반 웹 UI |
| Redis | 실시간 현재값 + 설정 DB (Pub/Sub 매개) |
| Prometheus + Exporter | 센서·제어 이력 DB (Exporter :9003가 Redis pull → Prometheus :9090). Pushgateway는 현재 비활성 |
| nginx | 리버스 프록시 (호스트 :80 → FastAPI :8000) |

## 구동 방법

### 사전 조건

- Python 3.11+
- Node.js 18+
- Redis 서버 실행 중 (`redis-server`)
- Prometheus + Exporter 실행 중 (Pushgateway는 현재 비활성)
- nginx (리버스 프록시 :80 → :8000)

### Local UI (PySide6)

```bash
cd src/local_ui
pip install -r requirements.txt
python main.py
```

### Web UI — Backend (FastAPI)

```bash
cd src/web_ui/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Web UI — Frontend (Svelte)

```bash
cd src/web_ui/frontend
npm install
npm run build      # 정적 프리렌더 빌드 (adapter-static → build/)
```

> 프로덕션은 별도 dev 서버가 없습니다. 프론트엔드는 정적 빌드되어 **FastAPI 백엔드(:8000)가 직접 서빙**하고, **nginx가 :80 → :8000** 으로 프록시합니다.

접속: `http://<RPi-IP>` (외부 브라우저 — IP는 Local UI Top bar에서 확인). 직접 백엔드 접속은 `http://<RPi-IP>:8000`.
