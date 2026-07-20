from __future__ import annotations

import inspect
import unittest

from app_control_protocol import ToolEventType

import wechat_desktop_tool
from _tool_test_fixtures import (
    FakeAppControl,
    _contradictory_predispatch_action_response,
    _visible_open_contact_responses,
)
from wechat_desktop_tool import (
    WeChatDesktopTool,
    execute_action_command,
    open_wechat_command,
    send_message_command,
)

from _tool_test_support import canonicalize_timing, command_trace


PUBLIC_EXPORTS = (
    "WECHAT_AGENT_SKILL_SCHEMA",
    "WECHAT_TOOL",
    "WECHAT_USE_SKILL_NAME",
    "WECHAT_USE_SKILL_RESOURCE",
    "WECHAT_WINDOW_SCHEMA",
    "WECHAT_FAILURE_KINDS",
    "AppControlClient",
    "WeChatAgentSkill",
    "WeChatAgentSkillFile",
    "WeChatActionableRegion",
    "WeChatChatPanel",
    "WeChatComposer",
    "WeChatConversationList",
    "WeChatConversationRow",
    "WeChatDesktopConfig",
    "WeChatDesktopTool",
    "WeChatElementRef",
    "WeChatFrame",
    "WeChatMessageList",
    "WeChatMessageRow",
    "WeChatNavigationItem",
    "WeChatOperation",
    "WeChatScrollRegion",
    "WeChatSearchBox",
    "WeChatToolbarButton",
    "WeChatVisibleMessage",
    "WeChatWindow",
    "__version__",
    "build_wechat_tool",
    "draft_message_command",
    "execute_action_command",
    "export_wechat_use_skill",
    "focus_contact_command",
    "inspect_window_command",
    "list_contacts_command",
    "list_conversations_command",
    "load_wechat_use_skill",
    "observe_current_chat_command",
    "open_contact_command",
    "open_wechat_command",
    "read_contact_messages_command",
    "read_visible_messages_command",
    "send_message_command",
    "send_message",
    "submit_draft_command",
    "wechat_command",
    "wechat_message_hash",
)


PUBLIC_SIGNATURES = {
    "__init__": (
        "(self, app_control: 'AppControlClient', "
        "config: 'WeChatDesktopConfig | None' = None) -> 'None'"
    ),
    "from_config": (
        "(app_control: 'AppControlClient', "
        'config: "\'AppControlConfig | Mapping[str, Any] | str | Path | None\'" '
        "= None, *, env: 'Mapping[str, str] | None' = None) -> "
        '"\'WeChatDesktopTool\'"'
    ),
    "run_command": (
        "(self, command: 'ToolCommand | Mapping[str, Any]', *, "
        "observer: 'ToolObserver | None' = None) -> 'ToolObservation'"
    ),
    "run_stream": (
        "(self, command: 'ToolCommand | Mapping[str, Any]', *, "
        "observer: 'ToolObserver | None' = None) -> 'Iterator[ToolEvent]'"
    ),
    "open_wechat": "(self) -> 'ToolObservation'",
    "inspect_window": (
        "(self, *, include_raw: 'bool' = False, "
        "include_actionables: 'bool' = True) -> 'ToolObservation'"
    ),
    "list_contacts": (
        "(self, *, limit: 'int' = 30, page_token: 'str | None' = None) "
        "-> 'ToolObservation'"
    ),
    "list_conversations": (
        "(self, *, limit: 'int' = 30, page_token: 'str | None' = None) "
        "-> 'ToolObservation'"
    ),
    "open_contact": "(self, contact: 'str') -> 'ToolObservation'",
    "execute_action": (
        "(self, action_ref: 'Mapping[str, JsonValue]') -> 'ToolObservation'"
    ),
    "focus_contact": "(self, contact: 'str') -> 'ToolObservation'",
    "observe_current_chat": (
        "(self, *, include_visible_messages: 'bool' = True) "
        "-> 'ToolObservation'"
    ),
    "read_visible_messages": "(self, *, limit: 'int' = 20) -> 'ToolObservation'",
    "read_contact_messages": (
        "(self, contact: 'str', *, limit: 'int' = 30) -> 'ToolObservation'"
    ),
    "draft_message": "(self, message: 'str') -> 'ToolObservation'",
    "submit_draft": (
        "(self, *, method: 'str' = 'keyboard_return') -> 'ToolObservation'"
    ),
    "send_message": (
        "(self, *, contact: 'str', message: 'str', "
        "verify_after_submit: 'bool' = False, verify_limit: 'int' = 20) "
        "-> 'ToolObservation'"
    ),
}


def _navigation_action_ref() -> dict[str, object]:
    return {
        "schema": "wechat.action_ref.v1",
        "id": "nav.contacts.press",
        "kind": "navigation.switch",
        "preferredMethod": "accessibility_action",
        "target": {
            "axPath": "0/2",
            "role": "AXRadioButton",
            "label": "通讯录",
            "actions": ["AXPress"],
        },
        "action": "AXPress",
        "preconditions": {
            "roleIn": ["AXRadioButton"],
            "labelIn": ["通讯录"],
            "actionIn": ["AXPress"],
        },
        "fallbacks": [
            {
                "method": "selector_click",
                "selector": {"role": "radio_button", "name": "通讯录"},
            }
        ],
    }


class WeChatToolEquivalenceTests(unittest.TestCase):
    maxDiff = None

    def test_public_exports_and_version_are_frozen(self) -> None:
        self.assertEqual(tuple(wechat_desktop_tool.__all__), PUBLIC_EXPORTS)
        self.assertEqual(wechat_desktop_tool.__version__, "0.3.0")
        self.assertIs(
            wechat_desktop_tool.WeChatDesktopTool,
            WeChatDesktopTool,
        )

    def test_public_tool_signatures_are_frozen(self) -> None:
        actual = {
            name: str(inspect.signature(getattr(WeChatDesktopTool, name)))
            for name in PUBLIC_SIGNATURES
        }

        self.assertEqual(actual, PUBLIC_SIGNATURES)

    def test_send_message_child_command_trace_is_frozen(self) -> None:
        app_control = FakeAppControl(_visible_open_contact_responses("Ada"))
        command = send_message_command(
            contact="Ada",
            message="hello",
            command_id="cmd_send",
        )

        result = WeChatDesktopTool(app_control).run_command(command)

        self.assertTrue(result.success)
        self.assertEqual(
            command_trace(app_control.commands),
            [
                {
                    "commandId": "cmd_send:focus_contact:open_contact:open_wechat",
                    "tool": "macos.computer_use",
                    "operation": "open_app",
                    "input": {
                        "app": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:focus_contact:open_contact",
                        "phase": "open_wechat",
                    },
                },
                {
                    "commandId": (
                        "cmd_send:focus_contact:open_contact:verify_wechat_window"
                    ),
                    "tool": "macos.computer_use",
                    "operation": "observe",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:focus_contact:open_contact",
                        "phase": "verify_wechat_window",
                    },
                },
                {
                    "commandId": (
                        "cmd_send:focus_contact:open_contact:"
                        "control_map_conversation_target_0"
                    ),
                    "tool": "macos.computer_use",
                    "operation": "accessibility_query",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "root": {"kind": "axPath", "axPath": "0/12/1/0"},
                        "query": {
                            "scope": "descendants",
                            "maxDepth": 2,
                            "limit": 2,
                            "timeBudgetMs": 450,
                            "attributes": [
                                "AXRole",
                                "AXDescription",
                                "AXPosition",
                                "AXSize",
                                "AXFrame",
                            ],
                            "actions": False,
                            "includeChildrenCount": False,
                            "match": {
                                "roleIn": ["AXCell"],
                                "descriptionContains": "Ada,",
                            },
                            "preferVisibleRows": True,
                        },
                        "includeRaw": False,
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:focus_contact:open_contact",
                        "phase": "control_map_conversation_target_0",
                    },
                },
                {
                    "commandId": (
                        "cmd_send:focus_contact:open_contact:"
                        "control_map_open_visible_contact"
                    ),
                    "tool": "macos.computer_use",
                    "operation": "accessibility_action",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "target": {
                            "kind": "axPath",
                            "axPath": "0/12/1/0/0",
                        },
                        "action": "AXPress",
                        "snapshotId": "frontmost:WeChat:微信 (聊天)",
                        "preconditions": {
                            "roleIn": ["AXRow"],
                            "actionIn": ["AXPress"],
                            "labelIn": ["Ada,hello,09:00"],
                        },
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:focus_contact:open_contact",
                        "phase": "control_map_open_visible_contact",
                    },
                },
                {
                    "commandId": "cmd_send:focus_contact:open_contact:verify_contact",
                    "tool": "macos.computer_use",
                    "operation": "accessibility_query",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "root": {"kind": "axPath", "axPath": "0/12/4"},
                        "query": {
                            "scope": "descendants",
                            "maxDepth": 2,
                            "limit": 20,
                            "timeBudgetMs": 1200,
                            "attributes": [
                                "AXRole",
                                "AXDescription",
                                "AXTitle",
                                "AXValue",
                                "AXFrame",
                            ],
                            "actions": False,
                            "includeChildrenCount": False,
                            "match": {"roleIn": ["AXStaticText"]},
                        },
                        "includeRaw": False,
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:focus_contact:open_contact",
                        "phase": "verify_contact",
                    },
                },
                {
                    "commandId": "cmd_send:draft_message:draft_message",
                    "tool": "macos.computer_use",
                    "operation": "type_text",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "text": "hello",
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:draft_message",
                        "phase": "draft_message",
                    },
                },
                {
                    "commandId": "cmd_send:submit_draft:submit_draft",
                    "tool": "macos.computer_use",
                    "operation": "press_key",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "key": "Return",
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_send:submit_draft",
                        "phase": "submit_draft",
                    },
                },
            ],
        )
        canonical = canonicalize_timing(result.to_dict())
        self.assertEqual(canonical["status"], "ok")
        self.assertEqual(
            canonical["observation"],
            {
                "focusedContact": "Ada",
                "messageHash": (
                    "sha256:2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e"
                    "73043362938b9824"
                ),
                "submitted": True,
                "verified": False,
                "verificationRequested": False,
            },
        )
        self.assertEqual(
            canonical["timing"],
            {"startedAt": "<startedAt>", "durationMs": "<durationMs>"},
        )

    def test_event_order_and_phase_names_are_frozen(self) -> None:
        events = list(
            WeChatDesktopTool(FakeAppControl()).run_stream(
                open_wechat_command(command_id="cmd_open")
            )
        )

        self.assertEqual(
            [event.event_type for event in events],
            [
                ToolEventType.STARTED,
                ToolEventType.PROGRESS,
                ToolEventType.PROGRESS,
                ToolEventType.OBSERVATION,
            ],
        )
        self.assertEqual([event.seq for event in events], [0, 1, 2, 3])
        self.assertEqual(
            [event.phase for event in events],
            [
                "open_wechat",
                "open_wechat",
                "verify_wechat_window",
                "open_wechat",
            ],
        )
        final = canonicalize_timing(events[-1].to_dict())
        self.assertEqual(final["summary"], "Opened or focused WeChat Desktop.")
        self.assertEqual(final["data"]["observation"]["status"], "ok")

    def test_contradictory_action_proof_never_replays_public_action(self) -> None:
        app_control = FakeAppControl(
            [_contradictory_predispatch_action_response(), {}]
        )
        command = execute_action_command(
            _navigation_action_ref(),
            command_id="cmd_action",
        )

        result = WeChatDesktopTool(app_control).run_command(command)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_failed")
        self.assertEqual(
            command_trace(app_control.commands),
            [
                {
                    "commandId": "cmd_action:execute_action",
                    "tool": "macos.computer_use",
                    "operation": "accessibility_action",
                    "input": {
                        "targetApp": "WeChat",
                        "bundleId": "com.tencent.xinWeChat",
                        "target": {"kind": "axPath", "axPath": "0/2"},
                        "action": "AXPress",
                        "preconditions": {
                            "roleIn": ["AXRadioButton"],
                            "labelIn": ["通讯录"],
                            "actionIn": ["AXPress"],
                        },
                    },
                    "timeoutMs": 30000,
                    "metadata": {
                        "sourceTool": "wechat.desktop",
                        "parentCommandId": "cmd_action",
                        "phase": "execute_action",
                    },
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
