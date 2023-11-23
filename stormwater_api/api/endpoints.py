import logging

from celery.result import AsyncResult
from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder

import stormwater_api.tasks as tasks
from stormwater_api.dependencies import cache, celery_app
from stormwater_api.models.calculation_input import StormwaterCalculationInput

logger = logging.getLogger(__name__)

router = APIRouter(tags=["jobs"])


@router.post("/execution")
async def process_job(
    calculation_input: StormwaterCalculationInput,
):
    if result := cache.get(key=calculation_input.celery_key):
        logger.info(
            f"Result fetched from cache with key: {calculation_input.celery_key}"
        )
        return {"result": result}

    logger.info(
        f"Result with key: {calculation_input.celery_key} not found in cache. Starting calculation ..."
    )
    result = tasks.compute_task.delay(jsonable_encoder(calculation_input))
    return {"job_id": result.id}


@router.get("/jobs/{job_id}/results")
async def get_job_results(job_id: str):
    async_result = AsyncResult(job_id, app=celery_app)

    response = {
        "job_id": async_result.id,
        "job_state": async_result.state,
        "job_succeeded": async_result.successful(),
        "result_ready": async_result.ready(),
    }

    if async_result.ready():
        response["result"] = async_result.get()

    return response


@router.get("/jobs/{job_id}/status")
async def get_job_status(job_id: str):
    async_result = AsyncResult(job_id, app=celery_app)
    state = async_result.state
    if state == "FAILURE":
        state = f"FAILURE : {str(async_result.get())}"

    return {"status": state}
