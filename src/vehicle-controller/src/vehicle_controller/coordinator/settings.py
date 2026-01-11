from vehicle_controller.settings import Settings


class CoordinatorSettings(Settings):
    heartbeat_interval: float
    heartbeat_missed_limit: int
