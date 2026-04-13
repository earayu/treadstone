# Re-export shim — canonical location: treadstone.infra.services.k8s_sync
from treadstone.infra.services.k8s_sync import *  # noqa: F401,F403
from treadstone.infra.services.k8s_sync import (  # noqa: F401
    _apply_metering_on_transition as _apply_metering_on_transition,
)
from treadstone.infra.services.k8s_sync import (
    _try_close_compute_session as _try_close_compute_session,
)
