from pathlib import Path
from typing import Any, Dict, Optional

import mat_ret.api as api
from mat_ret.databases import OptimadeSearchClient
from mat_ret.gui.workers import FetchWorker


class _MockResponse:
    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> Dict[str, Any]:
        return self._payload


def test_optimade_client_builds_elements_filter(monkeypatch, tmp_path: Path) -> None:
    captured: Dict[str, str] = {}

    def fake_get(url: str, params: Optional[Dict[str, str]] = None, timeout: int = 30):
        del url, timeout
        assert params is not None
        captured["filter"] = params["filter"]
        return _MockResponse(
            {
                "data": [
                    {
                        "id": "entry-1",
                        "attributes": {
                            "chemical_formula_reduced": "Fe2O3",
                        },
                    }
                ]
            }
        )

    monkeypatch.setattr("mat_ret.databases.requests.get", fake_get)

    client = OptimadeSearchClient(
        output_directory=tmp_path,
        providers=[{"id": "mock", "name": "Mock", "base_url": "https://mock.optimade.org"}],
        request_timeout=1,
    )
    results = client.get_structures("ignored", limit=2, elements=["Fe", "O"])

    assert captured["filter"] == 'elements HAS ALL "Fe", "O"'
    assert len(results) == 1


def test_fetch_worker_skips_unsupported_db_and_forwards_elements(monkeypatch) -> None:
    called = {"jarvis": 0, "oqmd": 0}
    received_kwargs: Dict[str, Any] = {}

    def fake_jarvis(formula: str, **kwargs):
        called["jarvis"] += 1
        received_kwargs["formula"] = formula
        received_kwargs.update(kwargs)
        return [{"formula": "Fe2O3"}]

    def fake_oqmd(formula: str, **kwargs):
        del formula, kwargs
        called["oqmd"] += 1
        return [{"formula": "Fe2O3"}]

    monkeypatch.setattr(api, "fetch_jarvis", fake_jarvis)
    monkeypatch.setattr(api, "fetch_oqmd", fake_oqmd)

    status_messages = []
    final_results: Dict[str, Any] = {}

    worker = FetchWorker(
        formula="Fe-O",
        databases=["oqmd", "jarvis"],
        query_mode="elements_all",
        elements=["Fe", "O"],
        limit=3,
    )

    worker.status_update.connect(status_messages.append)
    worker.finished_all.connect(final_results.update)
    worker.run()

    assert called["oqmd"] == 0
    assert called["jarvis"] == 1
    assert final_results["oqmd"] == []
    assert final_results["jarvis"] == [{"formula": "Fe2O3"}]
    assert received_kwargs["elements"] == ["Fe", "O"]
    assert any("skipped for element-set search" in msg for msg in status_messages)
