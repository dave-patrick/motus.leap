"""Startup script for tube-manager."""
from __future__ import annotations

import uvicorn

from tube_manager.api import api


def main():
    uvicorn.run(api.app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
