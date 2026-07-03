"""Public package for the macOS app-control backend."""

from app_control_protocol import AppControlConfig, HelperConfig, load_app_control_config
from .client import ComputerUseClient, MacOSComputerUseClient
from .commands import (
    COMPUTER_USE_TOOL,
    accessibility_action_command,
    accessibility_query_command,
    click_accessibility_command,
    click_command,
    click_coordinate_command,
    computer_use_command,
    focus_app_command,
    hotkey_command,
    observe_command,
    open_app_command,
    press_key_command,
    readiness_command,
    type_text_command,
    wait_command,
)
from .errors import COMPUTER_USE_FAILURE_KINDS, ComputerUseError
from .helper import (
    HelperDoctorReport,
    HelperManifest,
    HelperTransportClient,
    HelperTransportError,
    doctor_helper,
    helper_transport_from_manifest,
    load_helper_manifest,
)
from .models import (
    ComputerUseOperation,
    ComputerUseReadiness,
    ComputerUseReadinessStatus,
    ComputerUseResult,
    ComputerUseStatus,
    RiskDecision,
    RiskLevel,
)
from .policy import SafetyPolicy
from .readiness import DefaultPermissionProbe, PermissionProbe
from .service import (
    LocalCommandService,
    LocalServiceError,
    UnixSocketCommandService,
    UnixSocketServiceClient,
    send_service_payload,
    service_envelope_to_sse,
    service_envelopes_to_sse,
)

__version__ = "0.1.1"

__all__ = [
    "AppControlConfig",
    "ComputerUseClient",
    "ComputerUseOperation",
    "ComputerUseReadiness",
    "ComputerUseReadinessStatus",
    "ComputerUseResult",
    "ComputerUseStatus",
    "ComputerUseError",
    "COMPUTER_USE_FAILURE_KINDS",
    "COMPUTER_USE_TOOL",
    "DefaultPermissionProbe",
    "HelperDoctorReport",
    "HelperConfig",
    "HelperManifest",
    "HelperTransportClient",
    "HelperTransportError",
    "LocalCommandService",
    "LocalServiceError",
    "MacOSComputerUseClient",
    "PermissionProbe",
    "RiskDecision",
    "RiskLevel",
    "SafetyPolicy",
    "UnixSocketCommandService",
    "UnixSocketServiceClient",
    "__version__",
    "accessibility_query_command",
    "accessibility_action_command",
    "click_accessibility_command",
    "click_command",
    "click_coordinate_command",
    "computer_use_command",
    "doctor_helper",
    "focus_app_command",
    "helper_transport_from_manifest",
    "hotkey_command",
    "load_app_control_config",
    "load_helper_manifest",
    "observe_command",
    "open_app_command",
    "press_key_command",
    "readiness_command",
    "send_service_payload",
    "service_envelope_to_sse",
    "service_envelopes_to_sse",
    "type_text_command",
    "wait_command",
]
