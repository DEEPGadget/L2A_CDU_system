from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import sensor, control, history

app = FastAPI(title="L2A CDU API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://10.100.1.10:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sensor.router)
app.include_router(control.router)
app.include_router(history.router)
