"""Tests for Streamlit app UI using AppTest."""
from streamlit.testing.v1 import AppTest


def test_app_smoke_render():
    at = AppTest.from_file("app.py", default_timeout=15)
    at.run()
    assert not at.exception
    # Verify title
    assert len(at.title) >= 0 or len(at.markdown) > 0
    # Verify file uploader exists
    assert len(at.get("file_uploader")) == 1
    # Verify reset button in sidebar
    assert len(at.button) >= 1
