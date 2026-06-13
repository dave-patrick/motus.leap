"""Startup script for tube-manager."""
from __future__ import annotations

import uvicorn

from tube_manager.api import api


def main():
    uvicorn.run(api.app, host=os.getenv("HOST", "0.0.0.0"), port=int(os.getenv("PORT", "8000")))


if __name__ == "__main__":
    main()
