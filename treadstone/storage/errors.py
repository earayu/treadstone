"""Storage domain errors — backend readiness checks."""

from treadstone.core.errors import TreadstoneError

__all__ = [
    "StorageBackendNotReadyError",
    "StorageSnapshotBackendNotReadyError",
]


class StorageBackendNotReadyError(TreadstoneError):
    def __init__(self, storage_class_name: str):
        super().__init__(
            code="storage_backend_not_ready",
            message=(
                "Persistent sandbox storage is not ready. "
                f"StorageClass '{storage_class_name}' was not found in the cluster."
            ),
            status=503,
        )


class StorageSnapshotBackendNotReadyError(TreadstoneError):
    def __init__(self, snapshot_class_name: str):
        super().__init__(
            code="storage_snapshot_backend_not_ready",
            message=(
                "Cold snapshot storage is not ready. "
                f"VolumeSnapshotClass '{snapshot_class_name}' was not found in the cluster."
            ),
            status=503,
        )
