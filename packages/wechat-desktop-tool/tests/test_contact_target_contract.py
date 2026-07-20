from __future__ import annotations

from copy import deepcopy
from typing import Any
import unittest

from app_control_protocol import ToolObservation

from wechat_desktop_tool._contact_operations import (
    _open_visible_contact_phase,
    _open_visible_contact_with_control_map,
)

from test_tool import (
    FakeAppControl,
    WeChatDesktopTool,
    _accessibility_query_response,
    _failed_accessibility_query_response,
    _main_children_query_response,
    _normalized_node,
    _normalized_row,
    _top_level_query_response,
    wechat_command,
)


CONTACT = "Ada"
SENSITIVE_MESSAGE = "PRIVATE_MESSAGE_MUST_NOT_BE_DRAFTED"


def _open_with_control_map(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation | None:
    return _open_visible_contact_with_control_map(
        tool._runtime,
        *args,
        **kwargs,
    )


def _open_visible(
    tool: WeChatDesktopTool,
    *args: Any,
    **kwargs: Any,
) -> ToolObservation | None:
    return _open_visible_contact_phase(
        tool._runtime,
        *args,
        **kwargs,
    )


def _diagnostic_response(
    nodes: list[dict[str, object]],
    variant: str,
) -> dict[str, object]:
    response = _accessibility_query_response(nodes)
    diagnostics = response["observation"]["accessibilityQuery"]["diagnostics"]
    if variant == "integer_zero":
        diagnostics["truncated"] = 0
    elif variant == "string_false":
        diagnostics["truncated"] = "false"
    elif variant == "missing_flag":
        diagnostics.pop("truncated")
    elif variant == "none":
        diagnostics["truncated"] = None
    elif variant == "returned_nodes_none":
        diagnostics["returnedNodes"] = None
    else:
        raise AssertionError(variant)
    return response


def _search_send_responses(search_response: object) -> list[object]:
    return [
        {},
        _accessibility_query_response([]),
        _accessibility_query_response([]),
        _top_level_query_response(chats_selected=True),
        _accessibility_query_response([]),
        _top_level_query_response(chats_selected=True),
        _main_children_query_response(),
        {},
        {},
        {},
        {},
        search_response,
        {},
        _accessibility_query_response(
            [_normalized_node("0/11/4/2", "AXStaticText", value=CONTACT)]
        ),
        {},
        {},
    ]


class ContactTargetContractTests(unittest.TestCase):
    def test_malformed_completeness_never_mutates_any_target_path(self) -> None:
        cell = _normalized_node(
            "0/12/1/0/0/0",
            "AXCell",
            description="Ada,hello,09:00",
            x=330,
            y=120,
            width=270,
            height=64,
        )
        row = _normalized_row("0/11/1/0/0", "Ada,hello,09:00")
        for variant in (
            "integer_zero",
            "string_false",
            "missing_flag",
            "none",
            "returned_nodes_none",
        ):
            with self.subTest(path="control_map", variant=variant):
                app = FakeAppControl([_diagnostic_response([cell], variant)])
                result = _open_with_control_map(
                    WeChatDesktopTool(app),
                    wechat_command("open_contact", {"contact": CONTACT}),
                    contact=CONTACT,
                    evidence={},
                )

                assert result is not None
                self._assert_invalid_query_only(result, app)

            with self.subTest(path="selector_visible", variant=variant):
                app = FakeAppControl([_diagnostic_response([row], variant)])
                result = _open_visible(
                    WeChatDesktopTool(app),
                    wechat_command("open_contact", {"contact": CONTACT}),
                    contact=CONTACT,
                    main_content={"axPath": "0/11", "role": "AXSplitGroup"},
                    evidence={},
                )

                assert result is not None
                self._assert_invalid_query_only(result, app)

            with self.subTest(path="search", variant=variant):
                app = FakeAppControl(
                    _search_send_responses(_diagnostic_response([], variant))
                )
                result = WeChatDesktopTool(app).send_message(
                    contact=CONTACT,
                    message=SENSITIVE_MESSAGE,
                )

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, "accessibility_query_failed")
                self._assert_no_sensitive_operation_after_search_query(app)

    def test_first_incomplete_control_map_root_is_final(self) -> None:
        second_root_candidate = _normalized_node(
            "0/11/1/0/0/0",
            "AXCell",
            description="Ada,hello,09:00",
            x=330,
            y=120,
            width=270,
            height=64,
        )
        cases = {
            "truncated": _accessibility_query_response(
                [],
                truncated=True,
                truncation_reason="limit",
            ),
            "failed": _failed_accessibility_query_response(
                "accessibility_query_timeout",
                "First root timed out.",
                retryable=True,
            ),
            "invalid": _diagnostic_response([], "missing_flag"),
        }

        for case, first_response in cases.items():
            with self.subTest(case=case):
                app = FakeAppControl(
                    [
                        first_response,
                        _accessibility_query_response([second_root_candidate]),
                        {},
                    ]
                )
                result = _open_with_control_map(
                    WeChatDesktopTool(app),
                    wechat_command("open_contact", {"contact": CONTACT}),
                    contact=CONTACT,
                    evidence={},
                )

                assert result is not None
                self.assertFalse(result.success)
                self.assertEqual(
                    [command.operation for command in app.commands],
                    ["accessibility_query"],
                )

    def test_failed_visible_query_is_final_before_search_strategy(self) -> None:
        app = FakeAppControl(
            [
                _failed_accessibility_query_response(
                    "accessibility_query_timeout",
                    "Visible target query timed out.",
                    retryable=True,
                )
            ]
        )

        result = _open_visible(
            WeChatDesktopTool(app),
            wechat_command("open_contact", {"contact": CONTACT}),
            contact=CONTACT,
            main_content={"axPath": "0/11", "role": "AXSplitGroup"},
            evidence={},
        )

        assert result is not None
        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "accessibility_query_timeout")
        self.assertEqual(
            [command.operation for command in app.commands],
            ["accessibility_query"],
        )

    def test_failed_visible_query_blocks_full_send_strategy_continuation(self) -> None:
        responses = _search_send_responses(_accessibility_query_response([]))
        responses[4] = _failed_accessibility_query_response(
            "accessibility_query_timeout",
            "Visible target query timed out.",
            retryable=True,
        )
        app = FakeAppControl(responses)

        result = WeChatDesktopTool(app).send_message(
            contact=CONTACT,
            message=SENSITIVE_MESSAGE,
        )

        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "accessibility_query_timeout")
        phases = [
            command.metadata.get("phase") if command.metadata else None
            for command in app.commands
        ]
        failed_index = phases.index("visible_contact_rows")
        self.assertEqual(app.commands[failed_index + 1 :], [])
        typed = [
            command.input.get("text")
            for command in app.commands
            if command.operation == "type_text"
        ]
        self.assertNotIn(SENSITIVE_MESSAGE, typed)

    def test_search_candidate_set_must_be_unique_valid_and_in_window(self) -> None:
        offscreen = _normalized_row("0/11/search/0", CONTACT, y=-200)
        missing_frame = _normalized_row("0/11/search/0", CONTACT)
        missing_frame.pop("frame")
        malformed_frame = _normalized_row("0/11/search/0", CONTACT)
        malformed_frame["frame"] = {
            "x": "bad",
            "y": 100,
            "width": 200,
            "height": 58,
        }
        malformed_nodes = deepcopy(_accessibility_query_response([]))
        malformed_nodes["observation"]["accessibilityQuery"]["nodes"] = {
            "unexpected": "object"
        }
        malformed_nodes["observation"]["accessibilityQuery"]["diagnostics"][
            "returnedNodes"
        ] = 1
        cases = {
            "offscreen_only": (
                _accessibility_query_response([offscreen]),
                "wechat_action_target_unverified",
            ),
            "missing_frame_only": (
                _accessibility_query_response([missing_frame]),
                "wechat_action_target_unverified",
            ),
            "malformed_frame_only": (
                _accessibility_query_response([malformed_frame]),
                "wechat_action_target_unverified",
            ),
            "empty_complete": (
                _accessibility_query_response([]),
                "contact_not_found",
            ),
            "malformed_nodes_shape": (
                malformed_nodes,
                "accessibility_query_failed",
            ),
            "two_matches_one_offscreen": (
                _accessibility_query_response(
                    [
                        _normalized_row("0/11/search/0", CONTACT, y=-200),
                        _normalized_row("0/11/search/1", CONTACT, y=184),
                    ]
                ),
                "contact_ambiguous",
            ),
            "two_matches_in_window": (
                _accessibility_query_response(
                    [
                        _normalized_row("0/11/search/0", CONTACT, y=126),
                        _normalized_row("0/11/search/1", CONTACT, y=184),
                    ]
                ),
                "contact_ambiguous",
            ),
        }

        for case, (search_response, expected_failure) in cases.items():
            with self.subTest(case=case):
                app = FakeAppControl(_search_send_responses(search_response))
                result = WeChatDesktopTool(app).send_message(
                    contact=CONTACT,
                    message=SENSITIVE_MESSAGE,
                )

                self.assertFalse(result.success)
                self.assertEqual(result.failure_kind, expected_failure)
                self._assert_no_sensitive_operation_after_search_query(app)

    def _assert_invalid_query_only(self, result, app: FakeAppControl) -> None:
        self.assertFalse(result.success)
        self.assertEqual(result.failure_kind, "accessibility_query_failed")
        self.assertEqual(
            [command.operation for command in app.commands],
            ["accessibility_query"],
        )

    def _assert_no_sensitive_operation_after_search_query(
        self,
        app: FakeAppControl,
    ) -> None:
        phases = [
            command.metadata.get("phase") if command.metadata else None
            for command in app.commands
        ]
        query_index = phases.index("search_results")
        self.assertEqual(app.commands[query_index + 1 :], [])
        typed = [
            command.input.get("text")
            for command in app.commands
            if command.operation == "type_text"
        ]
        self.assertEqual(typed, [CONTACT])
        self.assertNotIn(SENSITIVE_MESSAGE, typed)


if __name__ == "__main__":
    unittest.main()
