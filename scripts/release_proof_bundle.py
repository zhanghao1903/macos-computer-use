#!/usr/bin/env python3
"""Build GitHub Release proof assets for strict PyPI publishing."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import sys
from typing import Any, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_preflight

REPO_ROOT = Path(__file__).resolve().parents[1]

PROOF_ASSET_NAMES = {
    "helper_doctor_report": "helper-doctor.json",
    "textedit_smoke_report": "textedit-smoke.json",
    "wechat_focus_draft_report": "wechat-focus-draft-smoke.json",
    "wechat_submit_report": "wechat-submit-smoke.json",
    "wechat_selector_engine_report": "wechat-selector-engine-smoke.json",
    "testpypi_install_report": "testpypi-install.json",
    "trusted_publisher_report": "trusted-publisher.json",
    "release_proof": "release-proof.json",
}


def build_bundle(
    *,
    output_dir: Path,
    helper_doctor_report: Path,
    textedit_smoke_report: Path,
    wechat_focus_draft_report: Path,
    wechat_submit_report: Path,
    wechat_selector_engine_report: Path,
    testpypi_install_report: Path,
    trusted_publisher_report: Path,
    expected_source_sha: str,
    sensitive_canaries: tuple[str, ...] = (),
) -> dict[str, object]:
    proof: dict[str, Any] = {}
    proof.update(release_preflight._load_helper_doctor_proof(helper_doctor_report))
    proof.update(release_preflight._load_textedit_smoke_proof(textedit_smoke_report))
    proof.update(
        release_preflight._load_wechat_smoke_proofs(
            (
                wechat_focus_draft_report,
                wechat_submit_report,
                wechat_selector_engine_report,
            ),
            expected_source_sha=expected_source_sha,
            sensitive_canaries=sensitive_canaries,
        )
    )
    if proof.get("wechat_selector_engine_smoke") is not True:
        raise ValueError("selector proof v2 did not satisfy strict validation")
    proof.update(
        release_preflight._load_testpypi_install_proof(
            REPO_ROOT,
            testpypi_install_report,
        )
    )
    proof.update(
        release_preflight._load_trusted_publisher_proof(trusted_publisher_report)
    )
    proof = {
        key: proof.get(key) is True
        for key in release_preflight.EXTERNAL_PROOFS
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    assets = {
        PROOF_ASSET_NAMES["helper_doctor_report"]: helper_doctor_report,
        PROOF_ASSET_NAMES["textedit_smoke_report"]: textedit_smoke_report,
        PROOF_ASSET_NAMES["wechat_focus_draft_report"]: wechat_focus_draft_report,
        PROOF_ASSET_NAMES["wechat_submit_report"]: wechat_submit_report,
        PROOF_ASSET_NAMES["wechat_selector_engine_report"]: (
            wechat_selector_engine_report
        ),
        PROOF_ASSET_NAMES["testpypi_install_report"]: testpypi_install_report,
        PROOF_ASSET_NAMES["trusted_publisher_report"]: trusted_publisher_report,
    }
    copied: list[dict[str, str]] = []
    for name, source in assets.items():
        target = output_dir / name
        _copy_asset(source, target)
        copied.append({"name": name, "path": str(target)})

    proof_path = output_dir / PROOF_ASSET_NAMES["release_proof"]
    proof_path.write_text(
        json.dumps(proof, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    copied.append(
        {"name": PROOF_ASSET_NAMES["release_proof"], "path": str(proof_path)}
    )
    missing_proofs = _missing_proofs(proof)
    return {
        "source": "release-proof-bundle",
        "outputDir": str(output_dir),
        "passed": not missing_proofs,
        "proof": proof,
        "missingProofs": missing_proofs,
        "assets": copied,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prepare strict release proof JSON assets for GitHub Release."
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--helper-doctor-report", type=Path, required=True)
    parser.add_argument("--textedit-smoke-report", type=Path, required=True)
    parser.add_argument("--wechat-focus-draft-report", type=Path, required=True)
    parser.add_argument("--wechat-submit-report", type=Path, required=True)
    parser.add_argument("--wechat-selector-engine-report", type=Path, required=True)
    parser.add_argument("--testpypi-install-report", type=Path, required=True)
    parser.add_argument("--trusted-publisher-report", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument(
        "--sensitive-canary",
        action="append",
        default=[],
        help="Sensitive value forbidden from selector proof v2; may be repeated.",
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Write assets even if one or more release proofs evaluate false.",
    )
    args = parser.parse_args(argv)

    report = build_bundle(
        output_dir=args.output_dir,
        helper_doctor_report=args.helper_doctor_report,
        textedit_smoke_report=args.textedit_smoke_report,
        wechat_focus_draft_report=args.wechat_focus_draft_report,
        wechat_submit_report=args.wechat_submit_report,
        wechat_selector_engine_report=args.wechat_selector_engine_report,
        testpypi_install_report=args.testpypi_install_report,
        trusted_publisher_report=args.trusted_publisher_report,
        expected_source_sha=args.expected_source_sha,
        sensitive_canaries=tuple(args.sensitive_canary),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if args.allow_incomplete or report["passed"] is True else 1


def _copy_asset(source: Path, target: Path) -> None:
    if source.resolve() == target.resolve():
        return
    shutil.copyfile(source, target)


def _missing_proofs(proof: dict[str, Any]) -> list[str]:
    return [
        key
        for key in release_preflight.EXTERNAL_PROOFS
        if proof.get(key) is not True
    ]


if __name__ == "__main__":
    sys.exit(main())
