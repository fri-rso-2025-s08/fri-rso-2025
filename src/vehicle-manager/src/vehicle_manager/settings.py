from typing import Annotated

from fastapi import Depends, Request
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    database_url: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


class Settings(DatabaseSettings, BaseSettings):
    tenant_id: str
    oauth_issuer_url: str
    oauth_jwks_url: str
    oauth_client_id: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


GetSettings = Annotated[Settings, Depends(get_settings)]
