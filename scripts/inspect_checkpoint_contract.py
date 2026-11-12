"""Inspect only already-downloaded configs and small normalizer tensors. No network/model loading."""

import argparse
import hashlib
import json
from pathlib import Path

from safetensors.numpy import load_file


def inspect(directory: Path) -> dict:
    config = json.loads((directory / "config.json").read_text())
    statistics = json.loads((directory / "dataset_statistics.json").read_text())
    files = {
        "config.json",
        "dataset_statistics.json",
        "policy_preprocessor.json",
        "policy_postprocessor.json",
    }
    tensor_summaries = {}
    for pipeline_name in ("policy_preprocessor.json", "policy_postprocessor.json"):
        pipeline = json.loads((directory / pipeline_name).read_text())
        for step in pipeline["steps"]:
            state_file = step.get("state_file")
            if state_file is None:
                continue
            if "normalizer" not in state_file or Path(state_file).name != state_file:
                raise ValueError(f"Unexpected state file: {state_file}")
            path = directory / state_file
            if path.stat().st_size > 64 * 1024:
                raise ValueError(
                    "Refusing to inspect a large tensor file; only tiny normalizers are allowed."
                )
            tensors = {key: value.tolist() for key, value in load_file(path).items()}
            for key, value in tensors.items():
                stream, quantile = key.split(".")
                if value != statistics[stream][quantile]:
                    raise ValueError(f"JSON/tensor statistics disagree for {state_file}:{key}")
            tensor_summaries[state_file] = tensors
            files.add(state_file)
    revisions = {
        (directory / ".cache" / "huggingface" / "download" / f"{name}.metadata").read_text().splitlines()[0]
        for name in files
    }
    if len(revisions) != 1:
        raise ValueError("Downloaded files do not all have the same Hub revision.")
    return {
        "repo_id": "black-forest-labs/flux-3-action-so101",
        "revision": revisions.pop(),
        "action_representation": config["action_representation"],
        "delta_absolute_dims": config["delta_absolute_dims"],
        "camera_keys": config["camera_keys"],
        "normalization_stats_in_config": config["normalization_stats"],
        "statistics": statistics,
        "normalizer_tensors": tensor_summaries,
        "numeric_unit_inference": (
            "indeterminate: all state quantiles are within +/-100"
            if all(abs(value) <= 100 for q in ("q01", "q99") for value in statistics["state"][q])
            else "state quantiles exceed RANGE_M100_100; consult the checkpoint's explicit units contract"
        ),
        "files": {
            name: {
                "bytes": (directory / name).stat().st_size,
                "sha256": hashlib.sha256((directory / name).read_bytes()).hexdigest(),
            }
            for name in sorted(files)
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = json.dumps(inspect(args.directory), indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
