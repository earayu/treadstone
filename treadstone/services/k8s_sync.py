# Re-export shim — canonical location: treadstone.infra.services.k8s_sync
from treadstone.infra.services.k8s_sync import *  # noqa: F401,F403
from treadstone.infra.services.k8s_sync import (  # noqa: F401
    _apply_metering_on_transition as _apply_metering_on_transition,
)
from treadstone.infra.services.k8s_sync import (
    _notify_observers_on_transition as _notify_observers_on_transition,
)
from treadstone.infra.services.k8s_sync import (
    _try_close_compute_session as _try_close_compute_session,
)

# Backward-compat: reconcile_metering/reconcile_storage_metering moved to
# treadstone.metering.services.metering_reconcile.  Re-export here so any
# existing callers using the old path continue to work.
from treadstone.metering.services.metering_reconcile import (  # noqa: F401
    reconcile_metering as reconcile_metering,
)
from treadstone.metering.services.metering_reconcile import (
    reconcile_storage_metering as reconcile_storage_metering,
)
