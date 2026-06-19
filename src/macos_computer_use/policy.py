"""Conservative risk policy for local desktop operations."""

from __future__ import annotations

import hashlib

from .models import ComputerUseOperation, RiskDecision, RiskLevel


HIGH_RISK_TERMS = frozenset(
    {
        "send",
        "submit",
        "delete",
        "pay",
        "purchase",
        "install",
        "authorize",
        "permission",
        "发送",
        "提交",
        "删除",
        "付款",
        "支付",
        "购买",
        "安装",
        "授权",
    }
)

SECURITY_TERMS = frozenset(
    {
        "password",
        "passcode",
        "credential",
        "security",
        "密码",
        "口令",
        "凭证",
        "安全",
    }
)


def _fingerprint(*parts: str | None) -> str:
    digest = hashlib.sha256()
    for part in parts:
        if part:
            digest.update(part.encode("utf-8"))
            digest.update(b"\0")
    return digest.hexdigest()[:24]


class SafetyPolicy:
    """Default local policy.

    The policy is intentionally lexical and conservative. It is not a semantic
    authorization system; callers must still own confirmation and audit.
    """

    def classify(
        self,
        operation: ComputerUseOperation,
        *,
        target: str | None = None,
        text: str | None = None,
        coordinate_click: bool = False,
        allow_coordinate_click: bool = False,
    ) -> RiskDecision:
        haystack = " ".join(part for part in (target, text) if part).lower()
        action_fingerprint = _fingerprint(operation.value, target, text)

        if any(term in haystack for term in SECURITY_TERMS):
            return RiskDecision(
                level=RiskLevel.HIGH,
                requires_confirmation=False,
                risk_label="security_or_password",
                reason="Security and password targets are not supported.",
                action_fingerprint=action_fingerprint,
            )

        if coordinate_click and not allow_coordinate_click:
            return RiskDecision(
                level=RiskLevel.HIGH,
                requires_confirmation=False,
                risk_label="coordinate_click_disabled",
                reason="Raw coordinate click is disabled by default.",
                action_fingerprint=action_fingerprint,
            )

        if operation == ComputerUseOperation.CLICK and any(
            term in haystack for term in HIGH_RISK_TERMS
        ):
            return RiskDecision(
                level=RiskLevel.HIGH,
                requires_confirmation=True,
                risk_label="high_risk_click",
                reason="Target appears to trigger an external or irreversible action.",
                action_fingerprint=action_fingerprint,
            )

        return RiskDecision(
            level=RiskLevel.LOW,
            requires_confirmation=False,
            reason="Operation is allowed by the default package policy.",
            action_fingerprint=action_fingerprint,
        )
