# PCB (Modbus Slave) — v1

> **버전**: v1 — 단순 R/W Slave. 모든 복잡한 시퀀스·예외 처리는 MCG(Master)가 담당.
> **v2** (OP_MODE / Watchdog / Auto Control 포함): [v2/PCB.md](../v2/PCB.md)

## 개요

- Modbus RTU Slave (MCG가 단일 Master)
- 센서 입력 수집 및 PWM / DOUT 제어 출력
- 모든 제어 로직·예외 처리·시퀀스는 MCG가 담당

---

## 기능

- 센서 입력 값 제공 (수온, 유량, 유압, 누수, 수위 등)
- 펌프 및 팬 제어 출력 수행 (PWM / DOUT)
- Modbus 레지스터 기반 Read / Write 지원
- Slave 설정 및 레지스터 맵은 PCB 명세서 기준으로 정의
