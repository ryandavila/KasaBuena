import asyncio

import pytest

from api.run_history import RunHistory


def test_history_bounded_and_exception_details_sanitized():
    history = RunHistory(limit=2)
    with history.track("scene", "request", "first"):
        pass
    with pytest.raises(RuntimeError), history.track("scene", "request", "second"):
        raise RuntimeError("private data")
    with (
        pytest.raises(asyncio.CancelledError),
        history.track("scene", "request", "third"),
    ):
        raise asyncio.CancelledError
    rows = history.all()
    assert [r.target for r in rows] == ["third", "second"]
    assert [r.result for r in rows] == ["cancelled", "error"]
    assert rows[1].error == "RuntimeError"
