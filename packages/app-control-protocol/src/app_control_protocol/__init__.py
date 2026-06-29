"""Shared protocol contracts for app-control tools."""

from .client import AppControlClient, StreamingAppControlClient
from .config import (
    AppControlConfig,
    ComputerUseConfig,
    HelperConfig,
    LoggingConfig,
    WeChatConfig,
    load_app_control_config,
)
from .event_logging import LoggingToolObserver, build_logging_observer
from .errors import ProtocolValidationError, ToolError
from .models import (
    COMMAND_SCHEMA,
    EVENT_SCHEMA,
    HELPER_REQUEST_SCHEMA,
    HELPER_RESPONSE_SCHEMA,
    OBSERVATION_SCHEMA,
    SERVICE_EVENT_SCHEMA,
    SERVICE_REQUEST_SCHEMA,
    SERVICE_RESPONSE_SCHEMA,
    ServiceAction,
    ServiceEventEnvelope,
    ServiceRequest,
    ServiceResponse,
    ServiceResponseStatus,
    ToolCommand,
    ToolEvent,
    ToolEventType,
    ToolObservation,
    ToolStatus,
)
from .observer import ToolObserver
from .schemas import (
    PROTOCOL_SCHEMA_FILES,
    ProtocolSchemaName,
    load_protocol_schema,
    load_protocol_schemas,
    protocol_schema_names,
    validate_protocol_payload,
)

__version__ = "0.1.0"

__all__ = [
    "COMMAND_SCHEMA",
    "EVENT_SCHEMA",
    "HELPER_REQUEST_SCHEMA",
    "HELPER_RESPONSE_SCHEMA",
    "OBSERVATION_SCHEMA",
    "SERVICE_EVENT_SCHEMA",
    "SERVICE_REQUEST_SCHEMA",
    "SERVICE_RESPONSE_SCHEMA",
    "AppControlConfig",
    "AppControlClient",
    "ComputerUseConfig",
    "HelperConfig",
    "LoggingConfig",
    "LoggingToolObserver",
    "ProtocolValidationError",
    "PROTOCOL_SCHEMA_FILES",
    "ProtocolSchemaName",
    "ServiceAction",
    "ServiceEventEnvelope",
    "ServiceRequest",
    "ServiceResponse",
    "ServiceResponseStatus",
    "StreamingAppControlClient",
    "ToolCommand",
    "ToolError",
    "ToolEvent",
    "ToolEventType",
    "ToolObservation",
    "ToolObserver",
    "ToolStatus",
    "WeChatConfig",
    "__version__",
    "build_logging_observer",
    "load_app_control_config",
    "load_protocol_schema",
    "load_protocol_schemas",
    "protocol_schema_names",
    "validate_protocol_payload",
]
