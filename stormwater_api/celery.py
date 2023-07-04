import json
import re
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import swmmio
from celery import Celery, signals
from celery.utils.log import get_task_logger

from redis import Redis
from stormwater_api.config import settings
from stormwater_api.models.calculation_input import CalculationTaskDefinition, Scenario

# from swmm.toolkit import output, shared_enum, solver


logger = get_task_logger(__name__)

DATA_DIR = (Path(__file__).parent / "data").resolve()
BLANK_GEOJSON = f"{DATA_DIR}/subcatchments.json"
# RUNOFF_ENUM = shared_enum.SubcatchAttribute.RUNOFF_RATE


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

    return perform_swmm_analysis(task_def.scenario, task_def.subcatchments)


# TODO add id to file json in case more requests are being processed
def save_subcatchments(subcatchments_geojson) -> None:
    # save geojson with subcatchments to disk
    with open(f"{DATA_DIR}/subcatchments.json", "w") as fp:
        json.dump(subcatchments_geojson, fp)


def make_inp_file(scenario: Scenario) -> None:
    baseline = swmmio.Model(f"{DATA_DIR}/input_files/{scenario.input_filename}")
    # reads updates to model from user input and updates the swmmio model
    if scenario.model_updates:
        subs = baseline.inp.subcatchments

        for update in scenario.model_updates:
            # update the outlet_id in the row of subcatchment_id

            subs.loc[update["subcatchment_id"], ["Outlet"]] = update["outlet_id"]
            baseline.inp.subcatchments = subs

    # Save the new model with the adjusted data
    new_file_path = f"{DATA_DIR}/scenario.inp"
    baseline.inp.save(new_file_path)


def perform_swmm_analysis(scenario: Scenario, subcatchments: dict):
    print("Creating input file...")
    make_inp_file(scenario)

    print("Saving subcatchments...")
    save_subcatchments(subcatchments)

    print("Computing scenario...")
    solver.swmm_run(
        f"{DATA_DIR}/scenario.inp",
        f"{DATA_DIR}/scenario.rpt",
        f"{DATA_DIR}/scenario.out",
    )
    time.sleep(1)

    return {
        "rain": get_rain_for(scenario.return_period),
        "geojson": get_result_geojson(),
    }


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

    df = pd.read_csv(
        f"{DATA_DIR}/rain_data/timeseries_"
        + str(return_period)
        + ".txt",  # get file for return period
        header=1,  # set row 1 as header
        delimiter=" ",  # delimiter is space
        skiprows=[2],  # ignore row number 2
    )

    return df["Value"].to_list()  # the rain amounts are in the column "Value"


# reads simulation duration and report_step_duration from inp file
def get_sim_duration_and_report_step():
    # initialize a model model object
    model = swmmio.Model(DATA_DIR + "/" + "scenario.inp")

    inp_start_date = model.inp.options.loc["START_DATE"].values[0]
    inp_start_time = model.inp.options.loc["START_TIME"].values[0]

    inp_end_date = model.inp.options.loc["END_DATE"].values[0]
    inp_end_time = model.inp.options.loc["END_TIME"].values[0]

    start_time = datetime.strptime(
        inp_start_date + " " + inp_start_time, "%d/%m/%Y %H:%M:%S"
    )
    end_time = datetime.strptime(inp_end_date + " " + inp_end_time, "%d/%m/%Y %H:%M:%S")
    report_step = datetime.strptime(
        model.inp.options.loc["REPORT_STEP"].values[0], "%H:%M:%S"
    ).minute

    simulation_duration = int((end_time - start_time).total_seconds() / 60)

    return simulation_duration, report_step


def get_result_geojson():
    sim_duration, report_step = get_sim_duration_and_report_step()

    _handle = output.init()
    output.open(_handle, "./data/scenario.out")

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
    geojson = load_geojson()
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


def load_geojson():
    with open(BLANK_GEOJSON, "r") as file:
        return json.load(file)


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
