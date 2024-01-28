import json
import time
from pathlib import Path

import pytest

TEST_CASES_DIR = Path(__file__).parent / "test_cases"


def wait_for_job_completion(client, endpoint, total_timeout=300):
    start_time = time.time()
    status = "PENDING"

    while status == "PENDING":
        time.sleep(5)

        if time.time() - start_time > total_timeout:
            raise Exception(
                f"Timeout reached. Job status still PENDING after {total_timeout} seconds."
            )

        response = client.get(endpoint)
        if response.status_code == 200:
            status = response.json().get("status")
            print(f"Job status: {status}")


def load_test_cases(directory: Path) -> list[dict]:

    json_data_list = []

    for file_path in directory.glob("*.json"):
        with open(file_path, "r") as file:
            data = json.loads(file.read())
            json_data_list.append(data)

    return json_data_list


@pytest.mark.parametrize(
    "test_case",
    load_test_cases(TEST_CASES_DIR),
)
def test_water_calculation(unauthorized_api_test_client, test_case):

    with unauthorized_api_test_client as client:
        response = client.post(
            "/stormwater/processes/runoff/execution", json=test_case["request"]
        )
        assert response.status_code == 200
        job_id = response.json()["job_id"]
        print(job_id)

        status_endpoint = f"/stormwater/jobs/{job_id}/status"
        wait_for_job_completion(client, status_endpoint)
        response = client.get(status_endpoint)
        assert response.json()["status"] == "SUCCESS"

        response = client.get(f"/stormwater/jobs/{job_id}/results")
        result = response.json()["result"]
        assert result == test_case["response"]
