import hashlib
import json

from pydantic import Field

from stormwater_api.models.base import BaseModelStrict


def hash_dict(dict_) -> str:
    dict_str = json.dumps(dict_, sort_keys=True)
    return hashlib.md5(dict_str.encode()).hexdigest()


class Scenario(BaseModelStrict):
    return_period: int = Field(..., alias="returnPeriod")
    flow_path: str = Field(..., alias="flowPath")
    roofs: str
    model_updates: list[dict] | None = Field(None, alias="modelUpdates")

    @property
    def input_filename(self) -> str:
        return f"{self.flow_path}_{self.roofs}_{self.return_period}.inp"


class CalculationInput(Scenario):
    city_pyo_user: str = Field(..., alias="cityPyoUser")


class CalculationTaskDefinition(BaseModelStrict):
    scenario: Scenario
    subcatchments: dict  # TODO create a model for the subcatchments

    @property
    def scenario_hash(self) -> str:
        return hash_dict(self.scenario.dict())

    @property
    def subcatchments_hash(self) -> str:
        return hash_dict(self.subcatchments)

    @property
    def celery_key(self) -> str:
        return f"{self.scenario_hash}_{self.subcatchments_hash}"
