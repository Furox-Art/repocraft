"""Contract tests for the tag-triggered publish workflow."""

from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github" / "workflows" / "publish.yml"


def test_publish_workflow_rejects_tag_version_mismatch() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "Verify tag matches package version" in text
    assert "RELEASE_TAG: ${{ github.ref_name }}" in text
    assert 'if tag != f"v{version}":' in text


def test_publish_workflow_tests_before_uploading() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert text.index("python -m pytest") < text.index("twine upload")
