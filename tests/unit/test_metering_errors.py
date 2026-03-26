"""Unit tests for metering error classes (F03)."""

from treadstone.core.errors import (
    ComputeQuotaExceededError,
    ConcurrentLimitError,
    SandboxDurationExceededError,
    StorageQuotaExceededError,
    TemplateNotAllowedError,
)


def test_compute_quota_exceeded_error():
    err = ComputeQuotaExceededError(monthly_used=100.0, monthly_limit=100.0, extra_remaining=0.0)
    d = err.to_dict()
    assert d["error"]["code"] == "compute_quota_exceeded"
    assert d["error"]["status"] == 402
    assert "100.0 / 100.0" in d["error"]["message"]
    assert "extra remaining: 0.0" in d["error"]["message"]


def test_storage_quota_exceeded_error():
    err = StorageQuotaExceededError(current_used_gib=8, requested_gib=5, total_quota_gib=10)
    d = err.to_dict()
    assert d["error"]["code"] == "storage_quota_exceeded"
    assert d["error"]["status"] == 402
    assert "8 GiB" in d["error"]["message"]
    assert "5 GiB" in d["error"]["message"]
    assert "available: 2 GiB" in d["error"]["message"]


def test_concurrent_limit_error():
    err = ConcurrentLimitError(current_running=3, max_concurrent=3)
    d = err.to_dict()
    assert d["error"]["code"] == "concurrent_limit_exceeded"
    assert d["error"]["status"] == 429
    assert "3 / 3" in d["error"]["message"]


def test_template_not_allowed_error():
    err = TemplateNotAllowedError(tier="free", template="medium", allowed_templates=["tiny", "small"])
    d = err.to_dict()
    assert d["error"]["code"] == "template_not_allowed"
    assert d["error"]["status"] == 403
    assert "'medium'" in d["error"]["message"]
    assert "'free'" in d["error"]["message"]
    assert "tiny, small" in d["error"]["message"]


def test_sandbox_duration_exceeded_error_hours_only():
    err = SandboxDurationExceededError(tier="free", max_duration_seconds=7200)
    d = err.to_dict()
    assert d["error"]["code"] == "sandbox_duration_exceeded"
    assert d["error"]["status"] == 400
    assert "2h" in d["error"]["message"]
    assert "'free'" in d["error"]["message"]


def test_sandbox_duration_exceeded_error_hours_and_minutes():
    err = SandboxDurationExceededError(tier="free", max_duration_seconds=5400)
    assert "1h30m" in err.message
