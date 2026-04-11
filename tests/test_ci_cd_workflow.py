"""Contract checks for CI/CD workflow container tagging and platforms."""

from pathlib import Path

import pytest

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "ci-cd.yml"


@pytest.fixture(scope="module")
def workflow_text() -> str:
    assert WORKFLOW.is_file(), f"Expected {WORKFLOW}"
    return WORKFLOW.read_text(encoding="utf-8")


def test_docker_latest_uses_prerelease_flag_not_substring_checks(workflow_text: str) -> None:
    assert "type=raw,value=latest,enable=${{ github.event_name == 'release' && !github.event.release.prerelease }}" in workflow_text
    assert "contains(github.ref_name, 'alpha')" not in workflow_text


def test_docker_experimental_for_develop_push_and_prerelease_releases(workflow_text: str) -> None:
    assert (
        "type=raw,value=experimental,enable=${{ (github.event_name == 'push' && github.ref == 'refs/heads/develop') || (github.event_name == 'release' && github.event.release.prerelease) }}"
        in workflow_text
    )


def test_multi_arch_only_on_release(workflow_text: str) -> None:
    assert (
        "platforms: ${{ github.event_name == 'release' && 'linux/amd64,linux/arm64' || 'linux/amd64' }}"
        in workflow_text
    )


def test_qemu_only_on_release(workflow_text: str) -> None:
    assert "if: github.event_name == 'release'" in workflow_text
    assert "docker/setup-qemu-action" in workflow_text
