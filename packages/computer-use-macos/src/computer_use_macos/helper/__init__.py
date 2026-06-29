"""Helper app lifecycle primitives for macOS computer-use."""

from .discovery import (
    DEFAULT_HELPER_MANIFEST_ENV_VARS,
    HelperDiscoveryResult,
    discover_helper_manifest,
    find_helper_manifest_path,
)
from .doctor import DoctorCheck, HelperDoctorReport, doctor_helper
from .launcher import HelperLaunchResult, launch_helper_app
from .manifest import (
    DEFAULT_HELPER_API_VERSION,
    HelperManifest,
    HelperManifestIdentityError,
    load_helper_manifest,
)
from .template import (
    HelperTemplateConfig,
    HelperTemplateResult,
    build_helper_template,
    init_helper_template,
)
from .transport import (
    HelperTransportClient,
    HelperTransportError,
    HelperTransportRequest,
    helper_transport_from_manifest,
)

__all__ = [
    "DEFAULT_HELPER_API_VERSION",
    "DEFAULT_HELPER_MANIFEST_ENV_VARS",
    "DoctorCheck",
    "HelperDiscoveryResult",
    "HelperDoctorReport",
    "HelperLaunchResult",
    "HelperManifest",
    "HelperManifestIdentityError",
    "HelperTemplateConfig",
    "HelperTemplateResult",
    "HelperTransportClient",
    "HelperTransportError",
    "HelperTransportRequest",
    "build_helper_template",
    "discover_helper_manifest",
    "doctor_helper",
    "find_helper_manifest_path",
    "helper_transport_from_manifest",
    "init_helper_template",
    "launch_helper_app",
    "load_helper_manifest",
]
