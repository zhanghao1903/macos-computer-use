"""Package exceptions and stable failure kind constants."""


class ComputerUseError(RuntimeError):
    """Base package error for unexpected local computer-use failures."""


UNSUPPORTED_TOOL = "unsupported_tool"
UNSUPPORTED_OPERATION = "unsupported_operation"
INVALID_INPUT = "invalid_input"

BACKEND_DISABLED = "backend_disabled"
UNSUPPORTED_PLATFORM = "unsupported_platform"
MISSING_ACCESSIBILITY = "missing_accessibility"
MISSING_SCREEN_RECORDING = "missing_screen_recording"
NEEDS_MANUAL_SETUP = "needs_manual_setup"
READINESS_ERROR = "error"

BLOCKED = "blocked"
NEEDS_USER = "needs_user"
NOT_AVAILABLE = "not_available"
TIMEOUT = "timeout"
FAILED = "failed"

SECURITY_OR_PASSWORD = "security_or_password"
COORDINATE_CLICK_DISABLED = "coordinate_click_disabled"
HIGH_RISK_CLICK = "high_risk_click"

INVALID_REQUEST = "invalid_request"
EMPTY_REQUEST = "empty_request"
INVALID_JSON = "invalid_json"
STREAM_REQUIRES_EVENT_LINES = "stream_requires_event_lines"
UNSUPPORTED_ACTION = "unsupported_action"

UNAUTHORIZED = "unauthorized"
APP_NOT_ALLOWLISTED = "app_not_allowlisted"
OPEN_APP_FAILED = "open_app_failed"
FOCUS_APP_FAILED = "focus_app_failed"
OBSERVE_FAILED = "observe_failed"
TARGET_NOT_FRONTMOST = "target_not_frontmost"
TYPE_TEXT_FAILED = "type_text_failed"
PRESS_KEY_FAILED = "press_key_failed"
HOTKEY_FAILED = "hotkey_failed"
CLICK_FAILED = "click_failed"
COORDINATE_CLICK_FAILED = "coordinate_click_failed"
TARGET_APP_NOT_RUNNING = "target_app_not_running"
FOCUSED_WINDOW_MISSING = "focused_window_missing"
SNAPSHOT_STALE = "snapshot_stale"
AX_PATH_NOT_FOUND = "ax_path_not_found"
PRECONDITION_FAILED = "precondition_failed"
UNSUPPORTED_ACCESSIBILITY_ACTION = "unsupported_accessibility_action"
ACCESSIBILITY_ACTION_FAILED = "accessibility_action_failed"

COMPUTER_USE_FAILURE_KINDS = (
    UNSUPPORTED_TOOL,
    UNSUPPORTED_OPERATION,
    INVALID_INPUT,
    BACKEND_DISABLED,
    UNSUPPORTED_PLATFORM,
    MISSING_ACCESSIBILITY,
    MISSING_SCREEN_RECORDING,
    NEEDS_MANUAL_SETUP,
    READINESS_ERROR,
    BLOCKED,
    NEEDS_USER,
    NOT_AVAILABLE,
    TIMEOUT,
    FAILED,
    SECURITY_OR_PASSWORD,
    COORDINATE_CLICK_DISABLED,
    HIGH_RISK_CLICK,
    INVALID_REQUEST,
    EMPTY_REQUEST,
    INVALID_JSON,
    STREAM_REQUIRES_EVENT_LINES,
    UNSUPPORTED_ACTION,
    UNAUTHORIZED,
    APP_NOT_ALLOWLISTED,
    OPEN_APP_FAILED,
    FOCUS_APP_FAILED,
    OBSERVE_FAILED,
    TARGET_NOT_FRONTMOST,
    TYPE_TEXT_FAILED,
    PRESS_KEY_FAILED,
    HOTKEY_FAILED,
    CLICK_FAILED,
    COORDINATE_CLICK_FAILED,
    TARGET_APP_NOT_RUNNING,
    FOCUSED_WINDOW_MISSING,
    SNAPSHOT_STALE,
    AX_PATH_NOT_FOUND,
    PRECONDITION_FAILED,
    UNSUPPORTED_ACCESSIBILITY_ACTION,
    ACCESSIBILITY_ACTION_FAILED,
)
