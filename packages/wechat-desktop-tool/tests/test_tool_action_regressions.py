from __future__ import annotations

import unittest

from _tool_test_fixtures import (
    Any,
    FakeAppControl,
    LoggingConfig,
    LoggingToolObserver,
    Path,
    RecordingObserver,
    StringIO,
    ToolStatus,
    WeChatDesktopTool,
    _accessibility_action_failure_with_observation,
    _accessibility_action_response,
    _click_node_phase_for_test,
    _contradictory_predispatch_action_response,
    _contradictory_unsupported_accessibility_action_response,
    _cross_package_action_fixture,
    _cross_package_click_node,
    _cross_package_focus_search,
    _definite_unsupported_accessibility_action_response,
    _failed_click_response,
    _legacy_unsupported_action_response,
    _mutated_unsupported_accessibility_action_response,
    _normalized_row,
    _precondition_failed_accessibility_action_response,
    _predispatch_accessibility_action_response,
    _production_action_fixture,
    _unsupported_accessibility_action_response,
    _unsupported_action_response_at_proof_location,
    _write_fake_accessibility_modules,
    action_safety_module,
    datetime,
    execute_action_command,
    json,
    os,
    patch,
    tempfile,
    timedelta,
    timezone,
    wechat_command,
)


class WeChatDesktopToolTests(unittest.TestCase):
    def test_execute_action_runs_accessibility_action_ref(self) -> None:
        app_control = FakeAppControl([_accessibility_action_response()])
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.operation, "execute_action")
        self.assertEqual(result.observation["schema"], "wechat.execute_action.v1")
        self.assertEqual(result.observation["actionId"], "nav.contacts.press")
        self.assertEqual(app_control.commands[0].operation, "accessibility_action")
        self.assertEqual(app_control.commands[0].input["target"]["axPath"], "0/2")
        self.assertEqual(
            app_control.commands[0].input["preconditions"]["labelIn"],
            ["通讯录"],
        )

    def test_execute_action_uses_selector_fallback_when_backend_unsupported(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _unsupported_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "selector_click")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )
        self.assertEqual(
            app_control.commands[1].input["selector"],
            {"role": "radio_button", "name": "通讯录"},
        )
        self.assertIn("execute_action:selector_fallback", result.evidence)

    def test_execute_action_does_not_republish_low_level_target_content(self) -> None:
        canary = "PRIVATE_ACTION_TARGET_CANARY"
        app_control = FakeAppControl(
            [
                _accessibility_action_response(
                    ax_path="0/2",
                    role="AXRadioButton",
                    label=canary,
                )
            ]
        )
        observer = RecordingObserver()
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "privacy.action",
            "kind": "navigation.switch",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/2",
                "role": "AXRadioButton",
                "label": canary,
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRadioButton"],
                "labelIn": [canary],
                "actionIn": ["AXPress"],
            },
        }

        result = WeChatDesktopTool(app_control).run_command(
            execute_action_command(
                action_ref,
                command_id="cmd_action_privacy",
            ),
            observer=observer,
        )

        self.assertTrue(result.success)
        serialized = json.dumps(
            {
                "result": result.to_dict(),
                "events": [event.to_dict() for event in observer.events],
            },
            ensure_ascii=False,
        )
        log_stream = StringIO()
        logging_observer = LoggingToolObserver(
            config=LoggingConfig(json=True, redact_text=True),
            stream=log_stream,
        )
        for event in observer.events:
            logging_observer.on_event(event)

        self.assertNotIn(canary, serialized)
        self.assertNotIn(canary, log_stream.getvalue())

    def test_execute_action_uses_one_fallback_for_definite_native_unsupported(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _definite_unsupported_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "selector_click")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_execute_action_blocks_contradictory_unsupported_effect(self) -> None:
        app_control = FakeAppControl(
            [_contradictory_unsupported_accessibility_action_response()]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_click_node_blocks_every_invalid_unsupported_action_proof(
        self,
    ) -> None:
        cases = (
            (
                "set_focus_proof_for_press_request",
                _definite_unsupported_accessibility_action_response(
                    action="AXSetFocus"
                ),
            ),
            (
                "cannot_complete_code",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"nativeErrorCode": -25204},
                    metadata_updates={"native_error_code": -25204},
                    nested_updates={"nativeErrorCode": -25204},
                ),
            ),
            (
                "wrong_action_code_pair",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"nativeErrorCode": -25205},
                    metadata_updates={"native_error_code": -25205},
                    nested_updates={"nativeErrorCode": -25205},
                ),
            ),
            (
                "missing_native_code",
                _mutated_unsupported_accessibility_action_response(
                    remove_top=("nativeErrorCode",),
                    remove_metadata=("native_error_code",),
                    remove_nested=("nativeErrorCode",),
                ),
            ),
            (
                "missing_action",
                _mutated_unsupported_accessibility_action_response(
                    remove_nested=("action",),
                ),
            ),
            (
                "missing_attempted",
                _mutated_unsupported_accessibility_action_response(
                    remove_top=("actionAttempted",),
                    remove_metadata=("action_attempted",),
                    remove_nested=("actionAttempted",),
                ),
            ),
            (
                "non_string_effect_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionEffect": {"value": "none"}},
                ),
            ),
            (
                "empty_effect_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionEffect": ""},
                ),
            ),
            (
                "contradictory_attempted_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"actionAttempted": False},
                ),
            ),
            (
                "non_integer_code_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={"nativeErrorCode": "-25206"},
                ),
            ),
            (
                "contradictory_failure_kind",
                _mutated_unsupported_accessibility_action_response(
                    nested_updates={
                        "failureKind": "accessibility_action_failed",
                    },
                ),
            ),
            (
                "contradictory_action_duplicate",
                _mutated_unsupported_accessibility_action_response(
                    top_updates={"action": "AXSetFocus"},
                ),
            ),
        )

        for label, response in cases:
            with self.subTest(label=label):
                app_control = FakeAppControl([response])
                tool = WeChatDesktopTool(app_control)

                result = _click_node_phase_for_test(
                    tool,
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_blocks_malformed_attempt_and_dispatch_evidence(
        self,
    ) -> None:
        cases = (
            (
                "truthy_attempted_string",
                _accessibility_action_failure_with_observation(
                    {"actionAttempted": "true"}
                ),
            ),
            (
                "falsey_attempted_string",
                _accessibility_action_failure_with_observation({"actionAttempted": ""}),
            ),
            (
                "conflicting_attempted_aliases",
                _accessibility_action_failure_with_observation(
                    {
                        "actionAttempted": False,
                        "action_attempted": True,
                    }
                ),
            ),
            (
                "malformed_action_container",
                _accessibility_action_failure_with_observation(
                    {"accessibilityAction": []}
                ),
            ),
            (
                "malformed_metadata_container",
                _accessibility_action_failure_with_observation({"metadata": []}),
            ),
            (
                "malformed_dispatch_duplicate",
                _accessibility_action_failure_with_observation(
                    {
                        "metadata": {
                            "accessibility_action_transport": {
                                "requestDispatched": False,
                            }
                        },
                        "accessibilityAction": {
                            "diagnostics": {"transport": {"request_dispatched": "true"}}
                        },
                    },
                    failure_kind="accessibility_action_timeout",
                    retryable=True,
                    status=ToolStatus.TIMEOUT,
                ),
            ),
            (
                "conflicting_dispatch_duplicate",
                _accessibility_action_failure_with_observation(
                    {
                        "metadata": {
                            "accessibility_action_transport": {
                                "requestDispatched": False,
                            }
                        },
                        "accessibilityAction": {
                            "diagnostics": {"transport": {"request_dispatched": True}}
                        },
                    },
                    failure_kind="accessibility_action_timeout",
                    retryable=True,
                    status=ToolStatus.TIMEOUT,
                ),
            ),
        )

        for label, response in cases:
            with self.subTest(label=label):
                app_control = FakeAppControl([response])
                result = _click_node_phase_for_test(
                    WeChatDesktopTool(app_control),
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_accepts_complete_proof_from_each_known_container(
        self,
    ) -> None:
        locations = (
            "observation_action",
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        for location in locations:
            with self.subTest(location=location):
                app_control = FakeAppControl(
                    [
                        _unsupported_action_response_at_proof_location(location),
                        {},
                    ]
                )
                result = _click_node_phase_for_test(
                    WeChatDesktopTool(app_control),
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertTrue(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action", "click"],
                )

    def test_click_node_blocks_conflicts_in_every_known_proof_container(
        self,
    ) -> None:
        locations = (
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        conflicting_updates = (
            {"action": "AXSetFocus"},
            {"actionAttempted": False},
            {"actionEffect": "performed"},
            {"nativeErrorCode": -25204},
            {"requestDispatched": False},
        )
        for location in locations:
            for updates in conflicting_updates:
                with self.subTest(location=location, updates=updates):
                    app_control = FakeAppControl(
                        [
                            _unsupported_action_response_at_proof_location(
                                location,
                                proof_updates=updates,
                                include_direct_proof=True,
                            )
                        ]
                    )
                    result = _click_node_phase_for_test(
                        WeChatDesktopTool(app_control),
                        wechat_command("open_contact", {"contact": "Ada"}),
                        _normalized_row("0/11/1/0/0", "Ada"),
                        phase="open_visible_contact",
                        evidence={},
                        snapshot_id="frontmost:WeChat:微信 (聊天)",
                    )

                    self.assertFalse(result.success)
                    self.assertEqual(
                        [command.operation for command in app_control.commands],
                        ["accessibility_action"],
                    )

    def test_click_node_blocks_malformed_known_proof_containers(self) -> None:
        locations = (
            "observation_action",
            "observation_diagnostics",
            "observation_transport",
            "metadata_transport",
            "result_evidence",
            "error_evidence",
        )
        for location in locations:
            with self.subTest(location=location):
                app_control = FakeAppControl(
                    [
                        _unsupported_action_response_at_proof_location(
                            location,
                            include_direct_proof=location != "observation_action",
                            malformed=True,
                        )
                    ]
                )
                result = _click_node_phase_for_test(
                    WeChatDesktopTool(app_control),
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_execute_action_precondition_failure_does_not_use_selector_fallback(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _precondition_failed_accessibility_action_response(),
                {},
            ]
        )
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
                    "selector": {
                        "role": "radio_button",
                        "name": "通讯录",
                    },
                }
            ],
        }

        result = tool.execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_precondition_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )
        self.assertIn("execute_action", result.error.evidence)
        self.assertNotIn("execute_action:selector_fallback", result.error.evidence)

    def test_execute_action_rejects_row_without_identity_precondition(
        self,
    ) -> None:
        app_control = FakeAppControl([_accessibility_action_response()])
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "chats.visible.0.open",
            "kind": "chats.open",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada,hello,09:00",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRow"],
                "actionIn": ["AXPress"],
            },
            "fallbacks": [
                {
                    "method": "selector_click",
                    "selector": {"role": "AXRow", "name": "Ada,hello,09:00"},
                }
            ],
        }

        result = WeChatDesktopTool(app_control).execute_action(action_ref)

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_precondition_failed")
        self.assertEqual(result.observation["actionId"], "chats.visible.0.open")
        self.assertEqual(app_control.commands, [])

    def test_execute_action_accepts_row_with_matching_identity_precondition(
        self,
    ) -> None:
        app_control = FakeAppControl(
            [
                _accessibility_action_response(
                    ax_path="0/12/1/0/0",
                    role="AXRow",
                    label="Ada,hello,09:00",
                )
            ]
        )
        action_ref = {
            "schema": "wechat.action_ref.v1",
            "id": "chats.visible.0.open",
            "kind": "chats.open",
            "preferredMethod": "accessibility_action",
            "target": {
                "axPath": "0/12/1/0/0",
                "role": "AXRow",
                "label": "Ada,hello,09:00",
                "actions": ["AXPress"],
            },
            "action": "AXPress",
            "preconditions": {
                "roleIn": ["AXRow"],
                "labelIn": ["Ada,hello,09:00"],
                "actionIn": ["AXPress"],
            },
        }

        result = WeChatDesktopTool(app_control).execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(
            app_control.commands[0].input["preconditions"]["labelIn"],
            ["Ada,hello,09:00"],
        )

    def test_execute_action_rejects_expired_action_ref_before_backend(self) -> None:
        expired_at = (
            (datetime.now(timezone.utc) - timedelta(seconds=1))
            .isoformat()
            .replace("+00:00", "Z")
        )
        for expires_at in (expired_at, "not-a-date"):
            with self.subTest(expires_at=expires_at):
                app_control = FakeAppControl([_accessibility_action_response()])
                tool = WeChatDesktopTool(app_control)
                action_ref = {
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
                    "expiresAt": expires_at,
                    "fallbacks": [
                        {
                            "method": "selector_click",
                            "selector": {
                                "role": "radio_button",
                                "name": "通讯录",
                            },
                        }
                    ],
                }

                result = tool.execute_action(action_ref)

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "wechat_action_ref_expired")
                self.assertEqual(
                    result.observation["schema"], "wechat.execute_action.v1"
                )
                self.assertEqual(result.observation["actionId"], "nav.contacts.press")
                self.assertEqual(app_control.commands, [])
                self.assertIn("actionRef", result.error.evidence)

    def test_execute_action_accepts_unexpired_action_ref(self) -> None:
        expires_at = (
            (datetime.now(timezone.utc) + timedelta(seconds=60))
            .isoformat()
            .replace("+00:00", "Z")
        )
        app_control = FakeAppControl([_accessibility_action_response()])
        tool = WeChatDesktopTool(app_control)
        action_ref = {
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
            "expiresAt": expires_at,
        }

        result = tool.execute_action(action_ref)

        self.assertTrue(result.success)
        self.assertEqual(result.observation["method"], "accessibility_action")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action"],
        )

    def test_click_node_phase_does_not_generate_coordinate_fallback(self) -> None:
        app_control = FakeAppControl([{}])
        tool = WeChatDesktopTool(app_control)
        command = wechat_command("open_contact", {"contact": "Ada"})
        evidence: dict[str, Any] = {}

        result = _click_node_phase_for_test(
            tool,
            command,
            {
                "axPath": "0/11/2",
                "role": "AXButton",
                "frame": {"x": 557, "y": 49, "width": 28, "height": 28},
            },
            phase="fallback_click",
            evidence=evidence,
        )

        self.assertTrue(result.success)
        self.assertEqual(app_control.commands[0].operation, "click")
        self.assertEqual(
            app_control.commands[0].input["selector"],
            {"role": "AXButton", "index": 1},
        )
        self.assertNotIn("coordinates", app_control.commands[0].input)

    def test_click_node_phase_rejects_unlabeled_row_before_coordinate(self) -> None:
        app_control = FakeAppControl()
        tool = WeChatDesktopTool(app_control)
        command = wechat_command("open_contact", {"contact": "Ada"})

        result = _click_node_phase_for_test(
            tool,
            command,
            {
                "axPath": "0/11/1/0/0",
                "role": "AXRow",
                "frame": {"x": 330, "y": 120, "width": 270, "height": 64},
            },
            phase="open_unlabeled_row",
            evidence={},
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "wechat_action_target_unverified")
        self.assertEqual(app_control.commands, [])

    def test_click_node_phase_allows_explicit_predispatch_fallback(self) -> None:
        app_control = FakeAppControl([_predispatch_accessibility_action_response(), {}])
        tool = WeChatDesktopTool(app_control)

        result = _click_node_phase_for_test(
            tool,
            wechat_command("open_contact", {"contact": "Ada"}),
            _normalized_row("0/11/1/0/0", "Ada"),
            phase="open_visible_contact",
            evidence={},
            snapshot_id="frontmost:WeChat:微信 (聊天)",
        )

        self.assertTrue(result.success)
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_legacy_and_predispatch_contradictions_never_replay(self) -> None:
        cases = (
            (
                "legacy_result_evidence_performed",
                _legacy_unsupported_action_response(
                    result_evidence={"actionEffect": "performed"},
                ),
            ),
            (
                "legacy_error_evidence_unknown",
                _legacy_unsupported_action_response(
                    error_evidence={"actionEffect": "unknown"},
                ),
            ),
            (
                "legacy_nested_cannot_complete",
                _legacy_unsupported_action_response(
                    observation={
                        "accessibilityAction": {"nativeErrorCode": -25204},
                    },
                ),
            ),
            (
                "predispatch_contradictory_effect_and_code",
                _contradictory_predispatch_action_response(),
            ),
        )
        coordinate_click_policy = (
            action_safety_module._should_try_coordinate_click_after_accessibility_action
        )
        policy_functions = (
            action_safety_module._should_fallback_from_accessibility_action,
            coordinate_click_policy,
            action_safety_module._should_press_return_for_search_result,
        )

        for label, response in cases:
            for policy in policy_functions:
                with self.subTest(label=label, policy=policy.__name__):
                    self.assertFalse(policy(response, expected_action="AXPress"))

            with self.subTest(label=label, caller="click_node"):
                app_control = FakeAppControl([response, {}])
                result = _click_node_phase_for_test(
                    WeChatDesktopTool(app_control),
                    wechat_command("open_contact", {"contact": "Ada"}),
                    _normalized_row("0/11/1/0/0", "Ada"),
                    phase="open_visible_contact",
                    evidence={},
                    snapshot_id="frontmost:WeChat:微信 (聊天)",
                )

                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )

    def test_click_node_phase_does_not_replay_failed_selector_fallback(self) -> None:
        app_control = FakeAppControl(
            [_unsupported_accessibility_action_response(), _failed_click_response()]
        )
        tool = WeChatDesktopTool(app_control)

        result = _click_node_phase_for_test(
            tool,
            wechat_command("open_contact", {"contact": "Ada"}),
            _normalized_row("0/11/1/0/0", "Ada"),
            phase="open_visible_contact",
            evidence={},
            snapshot_id="frontmost:WeChat:微信 (聊天)",
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "click_failed")
        self.assertEqual(
            [command.operation for command in app_control.commands],
            ["accessibility_action", "click"],
        )

    def test_cross_package_dispatched_action_failures_do_not_mutate_again(
        self,
    ) -> None:
        for mode in (
            "eof",
            "timeout",
            "malformed",
            "native_failure",
            "native_unsupported_contradictory",
            "native_unsupported_missing_effect",
            "native_unsupported_cannot_complete",
            "native_unsupported_wrong_code",
            "native_unsupported_missing_code",
            "native_unsupported_missing_action",
            "native_unsupported_attempted_false",
            "native_unsupported_invalid_effect",
            "native_unsupported_empty_effect",
            "native_unsupported_non_int_code",
            "legacy_unsupported_attempted",
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temp_dir:
                log_path = Path(temp_dir) / "requests.jsonl"
                client, worker, app_control, runner, tool = (
                    _cross_package_action_fixture(
                        mode,
                        log_path,
                        timeout_ms=200,
                    )
                )

                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_click_node(tool)
                finally:
                    worker.stop()

                requests = [
                    json.loads(line)
                    for line in log_path.read_text(encoding="utf-8").splitlines()
                ]
                self.assertFalse(result.success)
                self.assertEqual(result.retryable, False)
                self.assertEqual(len(requests), 1)
                self.assertEqual(requests[0]["action"], "AXPress")
                dispatch = (
                    action_safety_module._accessibility_action_request_dispatched(
                        result
                    )
                )
                self.assertTrue(dispatch.present)
                self.assertTrue(dispatch.valid)
                self.assertIs(dispatch.value, True)
                self.assertEqual(
                    [command.operation for command in app_control.commands],
                    ["accessibility_action"],
                )
                self.assertEqual(runner.calls, [])

    def test_cross_package_predispatch_failure_allows_one_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "requests.jsonl"
            client, worker, app_control, runner, tool = _cross_package_action_fixture(
                "timeout",
                log_path,
                timeout_ms=100,
            )

            try:
                worker.start()
                client._accessibility_action_worker = worker
                worker._lock.acquire()
                try:
                    result = _cross_package_click_node(tool)
                finally:
                    worker._lock.release()
            finally:
                worker.stop()

            self.assertTrue(result.success)
            self.assertFalse(log_path.exists())
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_unsupported_action_allows_one_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            log_path = Path(temp_dir) / "requests.jsonl"
            client, worker, app_control, runner, tool = _cross_package_action_fixture(
                "unsupported",
                log_path,
                timeout_ms=200,
            )

            try:
                worker.start()
                client._accessibility_action_worker = worker
                result = _cross_package_click_node(tool)
            finally:
                worker.stop()

            self.assertTrue(result.success)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_native_unsupported_press_allows_one_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir)
            _write_fake_accessibility_modules(module_dir)
            python_path = os.pathsep.join(
                item
                for item in (str(module_dir), os.environ.get("PYTHONPATH", ""))
                if item
            )
            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": python_path,
                    "FAKE_AX_ACTION": "AXPress",
                },
            ):
                client, worker, app_control, runner, tool = _production_action_fixture(
                    timeout_ms=500
                )
                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_click_node(tool, ax_path="0/0")
                finally:
                    worker.stop()

            self.assertTrue(result.success)
            native_result = app_control.observations[0]
            native_payload = native_result.observation["accessibilityAction"]
            self.assertEqual(native_payload["action"], "AXPress")
            self.assertEqual(native_payload["nativeErrorCode"], -25206)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click"],
            )
            self.assertEqual(runner.calls, [])

    def test_cross_package_native_unsupported_focus_allows_one_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            module_dir = Path(temp_dir)
            _write_fake_accessibility_modules(module_dir)
            python_path = os.pathsep.join(
                item
                for item in (str(module_dir), os.environ.get("PYTHONPATH", ""))
                if item
            )
            with patch.dict(
                os.environ,
                {
                    "PYTHONPATH": python_path,
                    "FAKE_AX_ACTION": "AXSetFocus",
                },
            ):
                client, worker, app_control, runner, tool = _production_action_fixture(
                    timeout_ms=500
                )
                try:
                    worker.start()
                    client._accessibility_action_worker = worker
                    result = _cross_package_focus_search(tool, ax_path="0/0")
                finally:
                    worker.stop()

            self.assertTrue(result.success)
            native_result = app_control.observations[0]
            native_payload = native_result.observation["accessibilityAction"]
            self.assertEqual(native_payload["action"], "AXSetFocus")
            self.assertEqual(native_payload["nativeErrorCode"], -25205)
            self.assertEqual(
                [command.operation for command in app_control.commands],
                ["accessibility_action", "click", "accessibility_query"],
            )
            self.assertEqual(runner.calls, [])


if __name__ == "__main__":
    unittest.main()
