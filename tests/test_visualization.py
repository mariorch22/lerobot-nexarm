from unittest.mock import MagicMock

import numpy as np
import pytest

from lerobot_robot_nexarm.visualization import RawTeleopViewer


@pytest.fixture
def rerun_backend(monkeypatch):
    import rerun as rr

    backend = MagicMock()
    # Exercise actual SDK archetypes/JPEG encoding, but forbid viewers and connections.
    for name in ("spawn", "init", "connect_grpc"):
        monkeypatch.setattr(
            rr, name, MagicMock(side_effect=AssertionError("Real Rerun connection forbidden"))
        )
    for name in ("log", "set_time", "send_blueprint"):
        monkeypatch.setattr(rr, name, getattr(backend, name))
    for name in ("init_rerun", "shutdown_rerun"):
        monkeypatch.setattr(f"lerobot.utils.visualization_utils.{name}", getattr(backend, name))
    return rr, backend


def test_live_frames_are_jpeg_compressed_temporal_and_have_explicit_times(rerun_backend):
    rr, backend = rerun_backend
    viewer = RawTeleopViewer()
    viewer.connect(["custom_scene"])
    backend.init_rerun.assert_called_once_with(session_name="nexarm_raw_teleoperation")
    backend.send_blueprint.assert_called_once()
    image = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    original = image.copy()
    for elapsed in (0.0, 0.1):
        viewer.log(
            observation={"custom_scene": image, "shoulder_pan.pos": 2100.0},
            action={"shoulder_pan.pos": 2200.0},
            elapsed=elapsed,
        )
    assert [call.kwargs for call in backend.set_time.call_args_list] == [
        {"duration": 0.0},
        {"duration": 0.1},
    ]
    assert all(call.args == ("teleop_time",) for call in backend.set_time.call_args_list)
    logs = backend.log.call_args_list
    assert len(logs) == 6
    assert all(call.kwargs == {"static": False} for call in logs)
    for call in logs:
        name, entity = call.args
        if name == "observation.custom_scene":
            assert isinstance(entity, rr.EncodedImage)
        else:
            assert name in ("observation.shoulder_pan.pos", "action.shoulder_pan.pos")
            assert isinstance(entity, rr.Scalars)
    np.testing.assert_array_equal(image, original)
    viewer.disconnect()
    viewer.disconnect()
    backend.shutdown_rerun.assert_called_once_with()


def test_failed_layout_setup_can_still_release_started_viewer(rerun_backend):
    _, backend = rerun_backend
    viewer = RawTeleopViewer()
    backend.send_blueprint.side_effect = RuntimeError("layout failed")
    with pytest.raises(RuntimeError, match="layout failed"):
        viewer.connect(["front", "wrist"])
    viewer.disconnect()
    backend.shutdown_rerun.assert_called_once_with()


def test_disconnecting_unstarted_viewer_does_not_initialize_rerun(rerun_backend):
    _, backend = rerun_backend
    RawTeleopViewer().disconnect()
    assert backend.mock_calls == []
