from pydantic import BaseSettings, Field


class Settings(BaseSettings):
    pod_termination_grace_period_seconds: int = Field(30)
    dapr_sidecar_http_port: int = Field(3500)
    main_app_port: int
    main_app_busy_probe_path: str = Field("/api/busy")
    main_app_ready_probe_path: str = Field("/api/ready")


def get_settings() -> Settings:
    return Settings()
