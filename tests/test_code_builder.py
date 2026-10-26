import pytest

from code_builder import CodeBuildError, _extract_json, validate_file_bundle


def test_extracts_json_manifest():
    data = _extract_json('{"files":[{"path":"app.py","content":"print(1)"}]}')
    assert data["files"][0]["path"] == "app.py"


def test_validates_and_prefixes_project_paths():
    files = validate_file_bundle({"files": [{"path": "src/app.py", "content": "print('ok')"}]})
    assert files == {"generated-project/src/app.py": "print('ok')"}


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", ".env", "src/.secret.py", "run.sh", "Dockerfile"])
def test_rejects_unsafe_paths_and_extensions(path):
    with pytest.raises(CodeBuildError):
        validate_file_bundle({"files": [{"path": path, "content": "no"}]})


def test_rejects_empty_or_oversized_manifest():
    with pytest.raises(CodeBuildError):
        validate_file_bundle({"files": []})
    with pytest.raises(CodeBuildError):
        validate_file_bundle({"files": [{"path": "app.py", "content": "x" * 30001}]})
