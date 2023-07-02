from stormwater_api.config import settings
from stormwater_api.swimdock.city_pyo import CityPyoClient

city_pyo_client = CityPyoClient(server_url=settings.city_pyo.url)
