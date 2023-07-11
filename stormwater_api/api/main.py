import io
from typing import Union

import uvicorn
from celery.result import AsyncResult
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import ValidationError

import stormwater_api.celery as tasks
from stormwater_api.celery import celery_app
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
    result = tasks.compute_task.delay(jsonable_encoder(processed_input))
    return {"taskId": result.id}


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    async_result = AsyncResult(task_id, app=celery_app)

    response = {
        "taskId": async_result.id,
        "taskState": async_result.state,
        "taskSucceeded": async_result.successful(),
        "resultReady": async_result.ready(),
    }
    if async_result.ready():
        response["result"] = async_result.get()

    return response


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=80)
