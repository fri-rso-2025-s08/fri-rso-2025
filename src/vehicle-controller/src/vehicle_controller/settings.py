from fastapi import FastAPI, Request
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    nats_url: str
    subject_heartbeat: str

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


def get_settings_from_fastapi[T: Settings](app: FastAPI, *, t: type[T]) -> T:
    ret = app.state.settings
    assert isinstance(ret, t)
    return ret


def get_settings[T: Settings](request: Request, *, t: type[T]) -> T:
    return get_settings_from_fastapi(request.app, t=t)
