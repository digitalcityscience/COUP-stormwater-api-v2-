from pydantic import BaseSettings, Field


class Redis(BaseSettings):
    # Available configs:
    # https://docs.celeryproject.org/en/stable/userguide/configuration.html#new-lowercase-settings

    redis_host: str = Field(..., env="REDIS_HOST")
    redis_port: int = Field(6379, env="REDIS_PORT")
    redis_pass: str = Field(6379, env="REDIS_PASS")

    # Worker config
    worker_concurrency: int = 10

    # Result config
    result_expires: bool = None  # Do not delete results from cache.
    result_persistent: bool = True
    enable_utc: bool = True
    task_default_queue: str = "swimdock"

    @property
    def redis_url(self) -> str:
        return f"redis://:{self.redis_pass}@{self.redis_host}:{self.redis_port}"

    @property
    def broker_url(self) -> str:
        return f"{self.redis_url}/0"

    @property
    def result_backend(self) -> str:
        return f"{self.redis_url}/1"


class CityPyo(BaseSettings):
    url: str = Field(..., env="CITY_PYO_URL")
    timeout_seconds: int = 30
    timeout_retry_count: int = 3
    timeout_retry_wait_seconds: int = 30


class Settings(BaseSettings):
    title: str = Field(..., env="APP_TITLE")
    description: str = Field(..., env="APP_DESCRIPTION")
    version: str = Field(..., env="APP_VERSION")
    debug: bool = Field(..., env="DEBUG")
    redis: Redis = Field(default_factory=Redis)
    city_pyo: CityPyo = Field(default_factory=CityPyo)


settings = Settings()
