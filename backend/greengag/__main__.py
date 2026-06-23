"""Thin entrypoint — run with: uvicorn greengag.main:app --reload"""

from greengag.main import app

__all__ = ["app"]
