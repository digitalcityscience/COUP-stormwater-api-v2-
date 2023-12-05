import hashlib
import json
from enum import auto

from fastapi.encoders import jsonable_encoder
from pydantic import validator

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
    return_period: int
    flow_path: FlowPath
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

    @property
    def scenario_hash(self) -> str:
        return hash_dict(
            {
                "return_period": self.return_period,
                "flow_path": self.flow_path,
                "roofs": self.roofs,
                "model_updates": jsonable_encoder(self.model_updates),
            }
        )

    @property
    def subcatchments_hash(self) -> str:
        return hash_dict(self.subcatchments)

    @property
    def celery_key(self) -> str:
        return f"{self.scenario_hash}_{self.subcatchments_hash}"
