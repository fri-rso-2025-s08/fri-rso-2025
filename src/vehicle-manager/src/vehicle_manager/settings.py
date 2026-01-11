from typing import Annotated

from fastapi import Depends, Request
from pydantic import computed_field
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

    nats_url: str
    subject_base: str

    @computed_field
    @property
    def sub_veh_base(self) -> str:
        return f"{self.subject_base}.veh"

    @computed_field
    @property
    def sub_veh_deltas(self) -> str:
        return f"{self.sub_veh_base}.deltas"

    @computed_field
    @property
    def sub_veh_cmd(self) -> str:
        return f"{self.sub_veh_base}.cmd"

    @computed_field
    @property
    def sub_veh_status(self) -> str:
        return f"{self.sub_veh_base}.status"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


GetSettings = Annotated[Settings, Depends(get_settings)]
