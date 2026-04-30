import importlib
from unittest import mock

import pytest

import plotting_service.routers.live_data as live_data_router
from plotting_service.services import live_data_service


def reload_live_data_modules(monkeypatch: pytest.MonkeyPatch, production: bool | None) -> tuple[object, object]:
    if production is None:
        monkeypatch.delenv("PRODUCTION", raising=False)
    else:
        monkeypatch.setenv("PRODUCTION", str(production).lower())

    reloaded_service = importlib.reload(live_data_service)
    reloaded_router = importlib.reload(live_data_router)
    return reloaded_service, reloaded_router


def test_get_live_data_directory_uses_staging_path_when_production_is_unset(tmp_path, monkeypatch):
    """Use the staging live-data directory when the PRODUCTION flag is
    unset."""
    live_data_service_module, _ = reload_live_data_modules(monkeypatch, production=None)
    live_data_path = tmp_path / "GENERIC-staging" / "livereduce" / "LOQ"
    live_data_path.mkdir(parents=True)

    assert live_data_service_module.get_live_data_directory("loq", str(tmp_path)) == live_data_path


def test_get_live_data_directory_uses_generic_path_when_production_is_true(tmp_path, monkeypatch):
    """Use the production live-data directory when the PRODUCTION flag is
    true."""
    live_data_service_module, _ = reload_live_data_modules(monkeypatch, production=True)
    live_data_path = tmp_path / "GENERIC" / "livereduce" / "LOQ"
    live_data_path.mkdir(parents=True)

    assert live_data_service_module.get_live_data_directory("loq", str(tmp_path)) == live_data_path


def test_get_live_data_directory_returns_none_when_selected_path_is_missing(tmp_path, monkeypatch):
    """Return None when the environment-selected live-data directory is
    absent."""
    live_data_service_module, _ = reload_live_data_modules(monkeypatch, production=False)
    (tmp_path / "GENERIC" / "livereduce" / "LOQ").mkdir(parents=True)

    assert live_data_service_module.get_live_data_directory("loq", str(tmp_path)) is None


@pytest.mark.asyncio
async def test_get_live_data_files_validates_staging_base_path(tmp_path, monkeypatch):
    """Validate listed files against the staging live-data base path."""
    _, live_data_router_module = reload_live_data_modules(monkeypatch, production=False)
    live_data_path = tmp_path / "GENERIC-staging" / "livereduce" / "LOQ"
    live_data_path.mkdir(parents=True)
    (live_data_path / "second.txt").write_text("second")
    (live_data_path / "first.txt").write_text("first")

    with (
        mock.patch.object(live_data_router_module, "CEPH_DIR", str(tmp_path)),
        mock.patch.object(live_data_router_module, "safe_check_filepath") as safe_check_filepath,
    ):
        files = await live_data_router_module.get_live_data_files("loq")

    assert files == ["first.txt", "second.txt"]
    safe_check_filepath.assert_called_once_with(live_data_path, str(tmp_path) + "/GENERIC-staging/livereduce")


@pytest.mark.asyncio
async def test_live_data_validates_production_base_path(tmp_path, monkeypatch):
    """Validate streamed live-data events against the production base path."""
    _, live_data_router_module = reload_live_data_modules(monkeypatch, production=True)
    live_data_path = tmp_path / "GENERIC" / "livereduce" / "LOQ"
    live_data_path.mkdir(parents=True)

    with (
        mock.patch.object(live_data_router_module, "CEPH_DIR", str(tmp_path)),
        mock.patch.object(live_data_router_module, "safe_check_filepath") as safe_check_filepath,
        mock.patch.object(
            live_data_router_module,
            "generate_file_change_events",
            return_value=iter([b"event: connected\ndata: {}\n\n"]),
        ) as generate_file_change_events,
    ):
        response = await live_data_router_module.live_data("loq")

    safe_check_filepath.assert_called_once_with(live_data_path, str(tmp_path) + "/GENERIC/livereduce")
    generate_file_change_events.assert_called_once_with(live_data_path, str(tmp_path), "loq", 30, 2)
    assert response.media_type == "text/event-stream"
    assert response.headers["X-Accel-Buffering"] == "no"
