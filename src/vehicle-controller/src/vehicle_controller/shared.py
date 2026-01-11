from pydantic import BaseModel


class Heartbeat(BaseModel):
    worker_id: str
    active: bool
