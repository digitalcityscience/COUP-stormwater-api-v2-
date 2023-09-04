import uvicorn
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from stormwater_api.api.endpoints import router as tasks_router
from stormwater_api.api.exception_handlers import (
    api_error_superclass_exception_handler,
    auth_exception_handler,
    validation_exception_handler,
)
from stormwater_api.auth.tokens import AuthError
from stormwater_api.config import settings
from stormwater_api.exceptions import StormwaterApiError

app = FastAPI(
    title=settings.title,
    descriprition=settings.description,
    version=settings.version,
)


@app.get("/health_check", tags=["ROOT"])
async def health_check():
    return "ok"


app.include_router(tasks_router)
app.add_exception_handler(AuthError, auth_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StormwaterApiError, api_error_superclass_exception_handler)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
