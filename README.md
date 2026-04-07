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
| Redis | 실시간 현재값 DB |
| Prometheus + Pushgateway | 센서·제어 이력 DB |

## 구동 방법

### 사전 조건

- Python 3.11+
- Node.js 18+
- Redis 서버 실행 중 (`redis-server`)
- Prometheus + Pushgateway 실행 중

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
npm run dev        # 개발 서버 (http://localhost:3000)
npm run build      # 프로덕션 빌드
```

접속: `http://10.100.1.10:3000` (외부 브라우저)
