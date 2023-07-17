from pathlib import Path

from celery import signals
from celery.utils.log import get_task_logger

from stormwater_api.dependencies import cache, celery_app
from stormwater_api.models.calculation_input import CalculationTask
from stormwater_api.processor import ScenarioProcessor

logger = get_task_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"
INPUT_DIR = DATA_DIR / "input_files"
OUTPUT_DIR = DATA_DIR / "output"
RAIN_DATA_DIR = DATA_DIR / "rain_data"


@celery_app.task()
def compute_task(task_def: CalculationTask) -> dict:
    task_def = CalculationTask(**task_def)
    if result := cache.get(key=task_def.celery_key):
        print(f"Result fetched from cache with key: {task_def.celery_key}")
        return result

    print(f"Result with key: {task_def.celery_key} not found in cache.")

    processor = ScenarioProcessor(
        task_definition=task_def,
        base_output_dir=OUTPUT_DIR,
        input_files_dir=INPUT_DIR,
        rain_data_dir=RAIN_DATA_DIR,
    )

    return processor.perform_swmm_analysis()


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get("state")
    args = kwargs.get("args")[0]
    result = kwargs.get("retval")

    if state == "SUCCESS":
        key = args["celery_key"]
        cache.put(key=key, value=result)
        print(f"Saved result with key {key} to cache.")
