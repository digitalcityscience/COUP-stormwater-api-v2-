import hashlib
import json
from enum import auto
from pydantic import Field, validator

from stormwater_api.models.base import BaseModelStrict, StrEnum


def hash_dict(dict_) -> str:
    dict_str = json.dumps(dict_, sort_keys=True)
    return hashlib.md5(dict_str.encode()).hexdigest()


class FlowPath(StrEnum):
    blockToStreet = auto()
    blockToPark = auto()


class Roofs(StrEnum):
    extensive = auto()
    intensive = auto()


class ModelUpdate(BaseModelStrict):
    outlet_id: str
    subcatchment_id: str


class StormwaterScenario(BaseModelStrict):
    return_period: int = Field(..., alias="returnPeriod")
    flow_path: FlowPath = Field(..., alias="flowPath")
    roofs: Roofs
    model_updates: list[ModelUpdate] | None
    

    @property
    def input_filename(self) -> str:
        return f"{self.flow_path}_{self.roofs}_{self.return_period}.inp"

    @validator("return_period")
    def validate_return_period(cls, v) -> int:
        assert v in [2, 10, 100], "Return period must be on of [2, 10, 100]"
        return v


class StormwaterCalculationInput(StormwaterScenario):
    subcatchments: dict
    result_format: str


class StormwaterTask(BaseModelStrict):
    scenario: StormwaterScenario
    subcatchments: dict

    @property
    def scenario_hash(self) -> str:
        return hash_dict(self.scenario.dict())

    @property
    def subcatchments_hash(self) -> str:
        return hash_dict(self.subcatchments)

    @property
    def celery_key(self) -> str:
        return f"{self.scenario_hash}_{self.subcatchments_hash}"
