from enum import Enum


class Role(str, Enum):
    ADMIN = "admin"
    RO = "ro"
    RW = "rw"

    def __str__(self) -> str:
        return str(self.value)
