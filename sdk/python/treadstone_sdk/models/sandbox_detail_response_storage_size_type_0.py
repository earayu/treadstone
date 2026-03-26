from enum import Enum


class SandboxDetailResponseStorageSizeType0(str, Enum):
    VALUE_0 = "5Gi"
    VALUE_1 = "10Gi"
    VALUE_2 = "20Gi"

    def __str__(self) -> str:
        return str(self.value)
