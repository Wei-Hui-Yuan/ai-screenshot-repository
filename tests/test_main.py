from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_library_page_is_served() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "AI Screenshot Repository" in response.text
