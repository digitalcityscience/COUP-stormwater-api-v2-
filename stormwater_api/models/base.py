from enum import Enum

import pydantic


class BaseModelStrict(pydantic.BaseModel):
    class Config:
        allow_mutation = False


class StrEnum(str, Enum):
    def _generate_next_value_(name, *_):
        return name
