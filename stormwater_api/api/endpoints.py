import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

import stormwater_api.tasks as tasks
from stormwater_api.dependencies import cache, celery_app, city_pyo_client
from stormwater_api.models.calculation_input import (
    StormwaterCalculationInput,
    StormwaterScenario,
    StormwaterTask,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


@router.post("/task")
async def process_swimdocktask(calculation_input: StormwaterCalculationInput):
    user_subcatchments = city_pyo_client.get_subcatchments(
        calculation_input.city_pyo_user
    )
    processed_input = StormwaterTask(
        scenario=StormwaterScenario(**calculation_input.dict(by_alias=True)),
        subcatchments=user_subcatchments,
    )
    if result := cache.get(key=processed_input.celery_key):
        logger.info(f"Result fetched from cache with key: {processed_input.celery_key}")
        return result

    logger.info(
        f"Result with key: {processed_input.celery_key} not found in cache. Starting calculation ..."
    )
    result = tasks.compute_task.delay(jsonable_encoder(processed_input))
    return {"taskId": result.id}


@router.get("/tasks/{task_id}")
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
