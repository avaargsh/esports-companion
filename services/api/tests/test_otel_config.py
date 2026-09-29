import pytest
from pydantic import ValidationError

from app.config import Settings


def test_otel_config_accepts_disabled_without_endpoint():
    settings = Settings(_env_file=None, otel_enabled=False)
    assert settings.otel_enabled is False


def test_otel_config_rejects_invalid_sample_ratio():
    with pytest.raises(ValidationError, match="OTEL_TRACE_SAMPLE_RATIO_OUT_OF_RANGE"):
        Settings(_env_file=None, otel_trace_sample_ratio=1.5)


def test_otel_config_requires_http_endpoint_when_enabled():
    with pytest.raises(
        ValidationError,
        match="OTEL_EXPORTER_OTLP_TRACES_ENDPOINT_INVALID",
    ):
        Settings(
            _env_file=None,
            otel_enabled=True,
            otel_exporter_otlp_traces_endpoint="collector:4318/v1/traces",
        )
