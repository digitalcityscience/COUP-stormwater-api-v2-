from typing import Optional

from pydantic import BaseModel


class StormwaterApiErrorResponse(BaseModel):
    message: str
    details: Optional[dict]

    @classmethod
    def internal_error(cls):
        # don't provide internal error details to external clients
        return cls(message="internal error")
