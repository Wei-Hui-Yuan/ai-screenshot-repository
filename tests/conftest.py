import pytest


@pytest.fixture(autouse=True)
def no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test can see a real Gemini key, so none can call the real API (rule 8).
    A test that needs a key sets a fake one itself."""
    for var in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(autouse=True)
def private_data_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: pytest.TempPathFactory) -> None:
    """Every test gets its own empty data folder, so none can touch the real data/
    (rule 9)."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))  # type: ignore[operator]
