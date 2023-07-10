import io
from typing import Union

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from stormwater_api.celery import compute_task
from stormwater_api.dependencies import city_pyo_client
from stormwater_api.models.calculation_input import (
    CalculationInput,
    CalculationTaskDefinition,
    Scenario,
)

app = FastAPI()


@app.get("/health_check", tags=["ROOT"])
async def health_check():
    return "ok"


@app.post("/task")
async def process_swimdocktask(calculation_input: CalculationInput):
    user_subcatchments = city_pyo_client.get_subcatchments(
        calculation_input.city_pyo_user
    )
    processed_input = CalculationTaskDefinition(
        scenario=Scenario(**calculation_input.dict(by_alias=True)),
        subcatchments=user_subcatchments,
    )
    compute_task(processed_input)
    return processed_input


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
