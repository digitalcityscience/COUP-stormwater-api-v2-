import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import swmmio
from celery import Celery, signals
from celery.utils.log import get_task_logger
from swmm.toolkit import output, shared_enum, solver

from redis import Redis
from stormwater_api.config import settings
from stormwater_api.models.calculation_input import (
    CalculationTaskDefinition,
    ModelUpdate,
    Scenario,
)

logger = get_task_logger(__name__)

DATA_DIR = Path(__file__).parent / "data"
INPUT_FILES = DATA_DIR / "input_files"
OUTPUT_DIR = DATA_DIR / "output"

# BLANK_GEOJSON = DATA_DIR / "subcatchments.json"
RUNOFF_ENUM = shared_enum.SubcatchAttribute.RUNOFF_RATE


def load_geojson(filepath: str) -> dict:
    with open(filepath, "r") as file:
        return json.load(file)


class Cache:
    def __init__(self, redis_client: Redis) -> None:
        self.redis_client = redis_client

    def save(self, key: str, value: dict) -> None:
        self.redis_client.set(key, json.dumps(value))

    def retrieve(self, key: str) -> dict:
        result = self.redis_client.get(key)
        return {} if result is None else json.loads(result)


redis_client = Redis(
    host=settings.redis.redis_host,
    port=settings.redis.redis_port,
    password=settings.redis.redis_pass,
)
cache = Cache(redis_client=redis_client)
celery_app = Celery(
    __name__, broker=settings.redis.broker_url, backend=settings.redis.result_backend
)


@celery_app.task()
def compute_task(task_def: CalculationTaskDefinition) -> dict:
    if result := cache.retrieve(key=task_def.celery_key):
        print(f"Result fetched from cache with key: {task_def.celery_key}")
        return result

    return perform_swmm_analysis(task_def)


def _update_model(updates: list[ModelUpdate], model: swmmio.Model) -> None:
    subs = model.inp.subcatchments
    for update in updates:
        # update the outlet_id in the row of subcatchment_id
        subs.loc[update.subcatchment_id, ["Outlet"]] = update.outlet_id
        model.inp.subcatchments = subs


# TODO add id to file json in case more requests are being processed
def save_subcatchments(subcatchments_geojson: dict, dest_path: Path) -> None:
    # save geojson with subcatchments to disk
    with open(dest_path, "w") as fp:
        json.dump(subcatchments_geojson, fp)


def make_inp_file_for(scenario: Scenario, scenario_output_path: Path) -> None:
    baseline = swmmio.Model(INPUT_FILES / scenario.input_filename)
    # reads updates to model from user input and updates the swmmio model
    if scenario.model_updates:
        _update_model(scenario.model_updates, baseline)

    # Save the new model with the adjusted data
    baseline.inp.save(scenario_output_path)


def perform_swmm_analysis(task_def: CalculationTaskDefinition) -> dict:
    print("Creating input file...")

    scenario_output_dir = OUTPUT_DIR / task_def.scenario_hash
    os.makedirs(scenario_output_dir, exist_ok=True)

    scenario_output_path = scenario_output_dir / "scenario.inp"
    make_inp_file_for(task_def.scenario, scenario_output_path)

    subcatchments_output_path = scenario_output_dir / "subcatchments.json"
    print("Saving subcatchments...")
    save_subcatchments(task_def.subcatchments, subcatchments_output_path)

    print("Computing scenario...")

    calculation_output_path = scenario_output_dir / "scenario.out"
    solver.swmm_run(
        str(scenario_output_path.resolve()),
        str((scenario_output_dir / "scenario.rpt").resolve()),
        str(calculation_output_path.resolve()),
    )
    time.sleep(1)

    return {
        "rain": get_rain_for(task_def.scenario.return_period),
        "geojson": get_result_geojson(
            scenario_output_path, calculation_output_path, subcatchments_output_path
        ),
    }
    # TODO delete file


# reads the relevant rain_data file for the calculation settings and returns the rain data as list
# I did try to read it directly from the scenario.inp/out/rpt files instead,
def get_rain_for(return_period: int) -> list:
    """
    example timeseries file
    SWIMM needs this format.

    ;;[TIMESERIES]
    ;;Name YY MM DD HH mm Value
    ;;---- -- -- -- -- -- -----
    2-yr 2021 01 01 00 00 1.143
    2-yr 2021 01 01 00 05 1.143
    """

    filename = DATA_DIR / "rain_data" / f"timeseries_{return_period}.txt"

    df = pd.read_csv(
        filename,
        header=1,  # set row 1 as header
        delimiter=" ",  # delimiter is space
        skiprows=[2],  # ignore row number 2
    )

    return df["Value"].to_list()  # the rain amounts are in the column "Value"


def _get_datetime_from_model(model: swmmio.Model, key_prefix: str) -> datetime:
    date_str = model.inp.options.loc[f"{key_prefix}_DATE"].values[0]
    time_str = model.inp.options.loc[f"{key_prefix}_TIME"].values[0]
    return datetime.strptime(date_str + " " + time_str, "%d/%m/%Y %H:%M:%S")


# reads simulation duration and report_step_duration from inp file
def get_sim_duration_and_report_step(scenario_path: Path) -> tuple[int, int]:
    # initialize a model model object
    model = swmmio.Model(str(scenario_path))

    start_time = _get_datetime_from_model(model, "START")
    end_time = _get_datetime_from_model(model, "END")
    simulation_duration = int((end_time - start_time).total_seconds() / 60)

    report_step = datetime.strptime(
        model.inp.options.loc["REPORT_STEP"].values[0], "%H:%M:%S"
    ).minute

    return simulation_duration, report_step


def get_result_geojson(
    scenario_path: Path, calculation_output_path: Path, subcatchments_path: Path
):
    sim_duration, report_step = get_sim_duration_and_report_step(scenario_path)

    _handle = output.init()
    output.open(_handle, str(calculation_output_path))

    subcatchment_count = output.get_proj_size(_handle)[0]

    # lookup table for result index by subcatchment name
    result_sub_indexes = {}
    for i in range(0, subcatchment_count):
        try:
            result_sub_indexes[
                output.get_elem_name(_handle, shared_enum.SubcatchResult, i)
            ] = i
        except Exception:
            print("missing a sub?? ", i)

    # iterate over subcatchemnt features in geojson and get timeseries results for subcatchment
    geojson = load_geojson(subcatchments_path)
    for feature in geojson["features"]:
        try:
            sub_id = result_sub_indexes[feature["properties"]["name_sub"]]
        except Exception:
            print("missing sub id in result", feature)
            continue

        run_offs = output.get_subcatch_series(
            _handle, sub_id, RUNOFF_ENUM, 0, sim_duration
        )
        timestamps = [i * report_step for i, val in enumerate(run_offs)]
        feature["properties"]["runoff_results"] = {
            "timestamps": timestamps,
            "runoff_value": run_offs,
        }

    output.close(_handle)

    return geojson


def is_valid_md5(checkme):
    if type(checkme) == str:
        if re.findall(r"([a-fA-F\d]{32})", checkme):
            return True

    return False


@signals.task_postrun.connect
def task_postrun_handler(task_id, task, *args, **kwargs):
    state = kwargs.get("state")
    args = kwargs.get("args")
    result = kwargs.get("retval")

    # only cache the "compute_task" task where the first 2 arguments are hashes
    if is_valid_md5(args[0]) and is_valid_md5(args[1]):
        # Cache only succeeded tasks
        if state == "SUCCESS":
            key = get_cache_key_compute_task(
                scenario_hash=args[0], subcatchments_hash=args[1]
            )
            cache.save(key=key, value=result)
            print("cached result with key %s" % key)


def get_cache_key_compute_task(**kwargs):
    return kwargs["scenario_hash"] + "_" + kwargs["subcatchments_hash"]
