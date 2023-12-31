import logging

from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from stormwater_api.api.responses import StormwaterApiErrorResponse
from stormwater_api.exceptions import StormwaterApiError

logger = logging.getLogger(__name__)


async def validation_exception_handler(request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=StormwaterApiErrorResponse(
            message="invalid input payload", details={"errors": exc.errors()}
        ).dict(),
    )


async def api_error_superclass_exception_handler(request, exc: StormwaterApiError):
    logger.error("Internal Stormwater API error", exc_info=exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=StormwaterApiErrorResponse.internal_error().dict(),
    )
