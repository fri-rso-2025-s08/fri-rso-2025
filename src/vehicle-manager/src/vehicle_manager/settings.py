from typing import Annotated

from fastapi import Depends, Request
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    database_url: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


class Settings(DatabaseSettings, BaseSettings):
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


GetSettings = Annotated[Settings, Depends(get_settings)]
