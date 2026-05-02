from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")


def _bool(val: str | None, default: bool = False) -> bool:
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes")


class Settings:
    backend_ws: str
    backend_rest: str
    pi_token_path: Path
    device_id: str
    log_level: str
    fake_hardware: bool

    def __init__(self) -> None:
        self.backend_ws = os.environ.get(
            "LARPCHEKR_BACKEND_WS", "ws://100.76.124.67:8000/ws/pi"
        )
        self.backend_rest = os.environ.get(
            "LARPCHEKR_BACKEND_REST", "http://100.76.124.67:8000"
        )
        self.pi_token_path = Path(
            os.environ.get("LARPCHEKR_PI_TOKEN_PATH", "/etc/larpchekr/pi_token")
        )
        self.device_id = os.environ.get("LARPCHEKR_DEVICE_ID", "rpi-dev-001")
        self.log_level = os.environ.get("LARPCHEKR_LOG_LEVEL", "info").upper()
        self.fake_hardware = _bool(os.environ.get("LARPCHEKR_FAKE_HARDWARE"), False)

    @property
    def pi_token(self) -> str:
        try:
            return self.pi_token_path.read_text().strip()
        except FileNotFoundError:
            if self.fake_hardware:
                return "dev-token"
            raise RuntimeError(
                f"Pi token not found at {self.pi_token_path}. "
                "Run scripts/pair.py first, or set LARPCHEKR_FAKE_HARDWARE=1 for dev."
            ) from None

    def configure_logging(self) -> None:
        logging.basicConfig(
            level=getattr(logging, self.log_level, logging.INFO),
            format="%(asctime)s %(levelname)-8s %(name)s %(message)s",
            datefmt="%H:%M:%S",
        )


settings = Settings()
