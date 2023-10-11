import json

from stormwater_api.tasks import perform_swmm_analysis


def test():
    with open("data/subcatchments.json", "r") as f:
        subcatchment_json = json.load(f)

    test_data = {
        # "city_pyo_user": "90af2ace6cb38ae1588547c6c20dcb36",
        "flow_path": "blockToPark",
        "roofs": "extensive",
        "return_period": 2,
        "model_updates": [],
    }

    perform_swmm_analysis(test_data, subcatchment_json)
