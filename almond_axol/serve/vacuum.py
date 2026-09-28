"""Optional left-arm LCUS-2 vacuum controls; never opens a device on startup."""

import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, StrictBool

from .vacuum_relay import VacuumRelay


class VacuumCommand(BaseModel):
    on: StrictBool


def install_vacuum_routes(app: FastAPI) -> None:
    device = os.environ.get("AXOL_SUCTION_DEVICE", "").strip()
    relay = VacuumRelay(device) if device else None

    @app.get("/api/vacuum")
    def status():
        if relay is None:
            return {"enabled": False, "commanded_on": None}
        return {"enabled": True, **relay.status()}

    @app.post("/api/vacuum")
    def command(body: VacuumCommand):
        if relay is None:
            raise HTTPException(503, "Set AXOL_SUCTION_DEVICE to the USB relay device")
        try:
            return {"enabled": True, **relay.set(body.on)}
        except OSError as exc:
            raise HTTPException(503, f"Vacuum relay unavailable: {exc}") from exc

    @app.post("/api/vacuum/release")
    def release():
        if relay is None:
            raise HTTPException(503, "Set AXOL_SUCTION_DEVICE to the USB relay device")
        try:
            return {"enabled": True, **relay.release()}
        except OSError as exc:
            raise HTTPException(503, f"Vacuum relay unavailable: {exc}") from exc
