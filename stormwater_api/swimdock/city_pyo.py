import requests
import tenacity

from stormwater_api.exceptions import StormwaterApiError


class CityPyoClientError(StormwaterApiError):
    """Base class for all CityPyo client errors."""

    ...


class CityPyoClient:
    """Class to handle CityPyo communication and users
    - Logs in all users listed in config and saves their user ids.
    - Gets data from cityPyo
    - Posts data to cityPyo
    """

    def __init__(
        self,
        server_url: str,
    ):
        self.server_url = server_url

    # returns subcatchments geojson as dict
    def get_subcatchments(self, user_id: str) -> dict:
        if subcatchments := self._get_layer_for_user(user_id, "subcatchments"):
            return subcatchments
        raise CityPyoClientError(
            f"Could not find subcatchments for user {user_id} on {self.server_url}."
        )

    # TODO discuss with Andre retry logic here
    # @tenacity.retry(
    #     # retry=tenacity.retry_if_exception_type(
    #     #     (TimeoutError, aiohttp.client_exceptions.ContentTypeError)
    #     # ),
    #     stop=tenacity.stop_after_attempt(settings.city_pyo.timeout_retry_count),
    #     wait=tenacity.wait_fixed(settings.city_pyo.timeout_retry_wait_seconds),
    #     reraise=True,
    # )
    def _get_layer_for_user(self, user_id: str, layer_name: str) -> dict:
        try:
            return self._call_city_pyo({"userid": user_id, "layer": layer_name})
        except requests.exceptions.RequestException as e:
            print(f"CityPyo error. {str(e)}")
            raise e

    def _call_city_pyo(self, data: dict) -> dict:
        response = requests.get(f"{self.server_url}/getLayer", json=data)
        if response.status_code == 200:
            return response.json()

        # TODO should this even be an error?
        raise CityPyoClientError(
            f"Response returned undesired status code: {response.status_code} "
            f"when fetching {data['layer']} for user {data['userid']}"
        )
