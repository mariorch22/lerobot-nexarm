"""Temporal, compressed Rerun preview for the raw NexArm teleoperation script."""

from collections.abc import Iterable

import numpy as np

from .bus import JOINT_NAMES


class RawTeleopViewer:
    def __init__(self):
        self._started = False

    def connect(self, camera_names: Iterable[str]) -> None:
        import rerun as rr
        import rerun.blueprint as rrb
        from lerobot.utils.visualization_utils import init_rerun

        init_rerun(session_name="nexarm_raw_teleoperation")
        self._started = True
        views = [rrb.Spatial2DView(origin=f"observation.{name}", name=name) for name in camera_names]
        views.extend(
            [
                rrb.TimeSeriesView(
                    contents=[f"observation.{name}.pos" for name in JOINT_NAMES], name="raw observations"
                ),
                rrb.TimeSeriesView(
                    contents=[f"action.{name}.pos" for name in JOINT_NAMES], name="raw targets"
                ),
            ]
        )
        rr.send_blueprint(rrb.Blueprint(rrb.Grid(*views)))

    def log(self, *, observation: dict, action: dict, elapsed: float) -> None:
        import rerun as rr

        rr.set_time("teleop_time", duration=elapsed)
        for name, value in observation.items():
            if isinstance(value, np.ndarray):
                # Live RGB frames belong on a timeline; static logs retain no frame timestamps.
                entity = rr.Image(value).compress(jpeg_quality=80)
            else:
                entity = rr.Scalars(float(value))
            rr.log(f"observation.{name}", entity, static=False)
        for name, value in action.items():
            rr.log(f"action.{name}", rr.Scalars(float(value)), static=False)

    def disconnect(self) -> None:
        if self._started:
            from lerobot.utils.visualization_utils import shutdown_rerun

            self._started = False
            shutdown_rerun()
