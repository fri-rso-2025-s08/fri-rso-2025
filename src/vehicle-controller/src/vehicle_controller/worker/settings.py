from pydantic import computed_field

from vehicle_controller.settings import Settings


class WorkerSettings(Settings):
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
