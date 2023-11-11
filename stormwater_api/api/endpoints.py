import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

import stormwater_api.tasks as tasks
from stormwater_api.dependencies import cache, celery_app
from stormwater_api.models.calculation_input import StormwaterCalculationInput

logger = logging.getLogger(__name__)

router = APIRouter(tags=["tasks"])


@router.post("/task")
async def process_swimdocktask(
    calculation_input: StormwaterCalculationInput,
):
    if result := cache.get(key=calculation_input.celery_key):
        logger.info(
            f"Result fetched from cache with key: {calculation_input.celery_key}"
        )
        return result

    logger.info(
        f"Result with key: {calculation_input.celery_key} not found in cache. Starting calculation ..."
    )
    result = tasks.compute_task.delay(jsonable_encoder(calculation_input))
    return {"task_id": result.id}


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    async_result = AsyncResult(task_id, app=celery_app)

    response = {
        "task_id": async_result.id,
        "task_state": async_result.state,
        "task_succeeded": async_result.successful(),
        "result_ready": async_result.ready(),
    }

    if async_result.ready():
        response["result"] = async_result.get()

    return response
