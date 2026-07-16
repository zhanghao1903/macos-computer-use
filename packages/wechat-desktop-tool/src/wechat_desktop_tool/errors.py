"""Stable failure kind constants for WeChat Desktop semantic operations."""

UNSUPPORTED_TOOL = "unsupported_tool"
UNSUPPORTED_OPERATION = "unsupported_operation"
INVALID_INPUT = "invalid_input"

WECHAT_OPEN_FAILED = "wechat_open_failed"
WECHAT_NOT_READY = "wechat_not_ready"
WECHAT_NOT_LOGGED_IN = "wechat_not_logged_in"
WECHAT_WINDOW_UNAVAILABLE = "wechat_window_unavailable"
WECHAT_NAVIGATION_FAILED = "wechat_navigation_failed"
WECHAT_NAVIGATION_TARGET_UNVERIFIED = "wechat_navigation_target_unverified"
WECHAT_NAVIGATION_POSTCONDITION_FAILED = (
    "wechat_navigation_postcondition_failed"
)
WECHAT_ACTION_FAILED = "wechat_action_failed"
WECHAT_ACTION_PRECONDITION_FAILED = "wechat_action_precondition_failed"
WECHAT_ACTION_REF_EXPIRED = "wechat_action_ref_expired"
WECHAT_ACTION_TARGET_UNVERIFIED = "wechat_action_target_unverified"
WECHAT_LIST_FAILED = "wechat_list_failed"
PAGINATION_NOT_SUPPORTED = "pagination_not_supported"
CONTACT_NOT_FOUND = "contact_not_found"
CONTACT_AMBIGUOUS = "contact_ambiguous"
CONTACT_NOT_FOCUSED = "contact_not_focused"
CONTACT_SEARCH_FAILED = "contact_search_failed"
SEARCH_NOT_FOCUSED = "search_not_focused"
SEARCH_FOCUS_FAILED = "search_focus_failed"
UNSAFE_SEARCH_HOTKEY = "unsafe_search_hotkey"
INPUT_NOT_FOCUSED = "input_not_focused"
DRAFT_FAILED = "draft_failed"
SUBMIT_FAILED = "submit_failed"
SUBMIT_UNKNOWN = "submit_unknown"
SEND_UNVERIFIED = "send_unverified"
MAIN_CONTENT_NOT_FOUND = "main_content_not_found"
MESSAGE_REGION_NOT_FOUND = "message_region_not_found"
QUERY_ROOT_NOT_FOUND = "query_root_not_found"
MISSING_ACCESSIBILITY = "missing_accessibility"
ACCESSIBILITY_QUERY_TIMEOUT = "accessibility_query_timeout"
APP_CONTROL_TRANSPORT_FAILED = "app_control_transport_failed"
ACCESSIBILITY_QUERY_FAILED = "accessibility_query_failed"
WECHAT_QUERY_TRUNCATED = "wechat_query_truncated"

FOCUS_FAILED = "focus_failed"
FOCUS_CONTACT_FAILED = "focus_contact_failed"
DRAFT_MESSAGE_FAILED = "draft_message_failed"
SUBMIT_DRAFT_FAILED = "submit_draft_failed"

WECHAT_FAILURE_KINDS = (
    UNSUPPORTED_TOOL,
    UNSUPPORTED_OPERATION,
    INVALID_INPUT,
    WECHAT_OPEN_FAILED,
    WECHAT_NOT_READY,
    WECHAT_NOT_LOGGED_IN,
    WECHAT_WINDOW_UNAVAILABLE,
    WECHAT_NAVIGATION_FAILED,
    WECHAT_NAVIGATION_TARGET_UNVERIFIED,
    WECHAT_NAVIGATION_POSTCONDITION_FAILED,
    WECHAT_ACTION_FAILED,
    WECHAT_ACTION_PRECONDITION_FAILED,
    WECHAT_ACTION_REF_EXPIRED,
    WECHAT_ACTION_TARGET_UNVERIFIED,
    WECHAT_LIST_FAILED,
    PAGINATION_NOT_SUPPORTED,
    CONTACT_NOT_FOUND,
    CONTACT_AMBIGUOUS,
    CONTACT_NOT_FOCUSED,
    CONTACT_SEARCH_FAILED,
    SEARCH_NOT_FOCUSED,
    SEARCH_FOCUS_FAILED,
    UNSAFE_SEARCH_HOTKEY,
    INPUT_NOT_FOCUSED,
    DRAFT_FAILED,
    SUBMIT_FAILED,
    SUBMIT_UNKNOWN,
    SEND_UNVERIFIED,
    MAIN_CONTENT_NOT_FOUND,
    MESSAGE_REGION_NOT_FOUND,
    QUERY_ROOT_NOT_FOUND,
    MISSING_ACCESSIBILITY,
    ACCESSIBILITY_QUERY_TIMEOUT,
    APP_CONTROL_TRANSPORT_FAILED,
    ACCESSIBILITY_QUERY_FAILED,
    WECHAT_QUERY_TRUNCATED,
    FOCUS_FAILED,
    FOCUS_CONTACT_FAILED,
    DRAFT_MESSAGE_FAILED,
    SUBMIT_DRAFT_FAILED,
)
