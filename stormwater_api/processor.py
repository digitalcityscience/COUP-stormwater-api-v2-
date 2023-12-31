import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import swmmio
from swmm.toolkit import output, shared_enum, solver

from stormwater_api.models.calculation_input import (
    ModelUpdate,
    StormwaterCalculationInput,
)

logger = logging.getLogger(__name__)

RUNOFF_ENUM = shared_enum.SubcatchAttribute.RUNOFF_RATE


def load_geojson(filepath: str) -> dict:
    with open(filepath, "r") as file:
        return json.load(file)


class ScenarioProcessor:
    def __init__(
        self,
        task_definition: StormwaterCalculationInput,
        base_output_dir: Path,
        input_files_dir: Path,
        rain_data_dir: Path,
    ) -> None:

        self.task = task_definition
        self.scenario_inp_path = input_files_dir / self.task.input_filename
        self.scenario_output_dir = base_output_dir / self.task.scenario_hash
        self.rain_data_dir = rain_data_dir

        self.scenario_output_path = str(self.scenario_output_dir / "scenario.inp")
        self.subcatchments_output_path = str(
            self.scenario_output_dir / "subcatchments.json"
        )
        self.calculation_output_path = str(self.scenario_output_dir / "scenario.out")
        self.rpt_file_output_path = str(self.scenario_output_dir / "scenario.rpt")

    def perform_swmm_analysis(self):
        os.makedirs(self.scenario_output_dir, exist_ok=True)

        logger.info("Creating input file...")
        self._make_inp_file()

        logger.info("Saving subcatchments...")
        self._save_subcatchments(
            self.task.subcatchments, self.subcatchments_output_path
        )

        logger.info("Computing scenario...")
        solver.swmm_run(
            self.scenario_output_path,
            self.rpt_file_output_path,
            self.calculation_output_path,
        )
        time.sleep(1)

        return {
            "rain": self._get_rain_for(self.task.return_period),
            "geojson": self._get_result_geojson(),
        }

    # reads the relevant rain_data file for the calculation settings and returns the rain data as list
    # I did try to read it directly from the scenario.inp/out/rpt files instead,
    def _get_rain_for(self, return_period: int) -> list:
        """
        example timeseries file
        SWIMM needs this format.

        ;;[TIMESERIES]
        ;;Name YY MM DD HH mm Value
        ;;---- -- -- -- -- -- -----
        2-yr 2021 01 01 00 00 1.143
        2-yr 2021 01 01 00 05 1.143
        """

        filename = self.rain_data_dir / f"timeseries_{return_period}.txt"

        df = pd.read_csv(
            filename,
            header=1,  # set row 1 as header
            delimiter=" ",  # delimiter is space
            skiprows=[2],  # ignore row number 2
        )

        return df["Value"].to_list()  # the rain amounts are in the column "Value"

    def _make_inp_file(self) -> None:
        logger.info("Making inp file ...")
        baseline = swmmio.Model(self.scenario_inp_path)

        if self.task.model_updates:
            self._update_model(self.task.model_updates, baseline)

        baseline.inp.save(self.scenario_output_path)

    @staticmethod
    def _update_model(updates: list[ModelUpdate], model: swmmio.Model) -> None:
        logger.info("Updating model...")

        subs = model.inp.subcatchments
        for update in updates:
            # update the outlet_id in the row of subcatchment_id
            subs.loc[update.subcatchment_id, ["Outlet"]] = update.outlet_id
            model.inp.subcatchments = subs

        logger.info("Scenario updated...")

    @staticmethod
    def _save_subcatchments(subcatchments_geojson: dict, dest_path: Path) -> None:
        with open(dest_path, "w") as fp:
            json.dump(subcatchments_geojson, fp)

    @staticmethod
    def _get_datetime_from_model(model: swmmio.Model, key_prefix: str) -> datetime:
        date_str = model.inp.options.loc[f"{key_prefix}_DATE"].values[0]
        time_str = model.inp.options.loc[f"{key_prefix}_TIME"].values[0]
        datetime_str = f"{date_str} {time_str}"
        return datetime.strptime(datetime_str, "%d/%m/%Y %H:%M:%S")

    # reads simulation duration and report_step_duration from inp file
    def _get_sim_duration_and_report_step(self) -> tuple[int, int]:
        model = swmmio.Model(self.scenario_output_path)
        start_time = self._get_datetime_from_model(model, "START")
        end_time = self._get_datetime_from_model(model, "END")
        simulation_duration = int((end_time - start_time).total_seconds() / 60)

        report_step = datetime.strptime(
            model.inp.options.loc["REPORT_STEP"].values[0], "%H:%M:%S"
        ).minute

        return simulation_duration, report_step

    def _clean_up(self) -> None:
        # deletes all files created by the calculation
        directory_path = Path(self.scenario_output_dir)

        # Ensure the provided path is a directory
        if not directory_path.is_dir():
            raise ValueError("The provided path is not a valid directory.")

        # Iterate over all items (files and directories) in the directory
        for item in directory_path.glob("**/*"):
            if item.is_file():
                item.unlink()  # Delete the file

    def _get_result_geojson(
        self,
    ):
        sim_duration, report_step = self._get_sim_duration_and_report_step()

        _handle = output.init()
        output.open(_handle, self.calculation_output_path)

        subcatchment_count = output.get_proj_size(_handle)[0]

        # lookup table for result index by subcatchment name
        result_sub_indexes = {}
        for i in range(subcatchment_count):
            try:
                result_sub_indexes[
                    output.get_elem_name(_handle, shared_enum.SubcatchResult, i)
                ] = i
            except Exception:
                logger.info("missing a sub?? ", i)

        # iterate over subcatchemnt features in geojson and get timeseries results for subcatchment
        geojson = load_geojson(self.subcatchments_output_path)
        for feature in geojson["features"]:
            try:
                sub_id = result_sub_indexes[feature["properties"]["name_sub"]]
            except Exception:
                logger.info("missing sub id in result", feature)
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
        self._clean_up()

        return geojson
