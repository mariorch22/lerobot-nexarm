# /// script
# requires-python = ">=3.12"
# dependencies = ["vastai>=1.11,<2", "python-dotenv>=1,<2"]
# ///
"""Rent the cheapest RTX 5090 on vast.ai and serve FLUX 3 Action on it.

    uv run cloud/deploy.py up        rent (or reuse) the instance, install, load the model, open the tunnel
    uv run cloud/deploy.py status    show our instance and whether the API answers
    uv run cloud/deploy.py down      stop the instance (add --destroy to delete it and its disk)

LoRA training on the same instance (see docs/LORA.md):

    uv run cloud/deploy.py train --dataset outputs/datasets/NAME    upload the dataset, start training
                                 (--steps 40 for a short trial run)
    uv run cloud/deploy.py logs      GPU memory and the live training log
    uv run cloud/deploy.py fetch     download the trained adapter; do this before `down --destroy`
    uv run cloud/deploy.py up --adapter outputs/lora/nexarm_lora/pretrained_model   serve with the adapter

`up` costs money. It ends by holding an SSH tunnel open: the API is then at
http://127.0.0.1:8000 until Ctrl+C. Ctrl+C only closes the tunnel, `down` stops the billing.
Keys come from cloud/.env (VASTAI_API_KEY, HF_TOKEN); see .env.example.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tarfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
LABEL = "nexarm-f3a"  # how we recognise our own instance in the vast.ai account
IMAGE = "nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04"
DISK_GB = 120  # environment and weights need about 40 GB; the disk cannot be grown later
KNOWN_HOSTS = HERE / ".known_hosts"

# Vast.ai search filter. Memory fields are in MB.
OFFER_QUERY = {
    "gpu_name": {"eq": "RTX 5090"},
    "num_gpus": {"eq": 1},
    "cpu_ram": {"gte": 64_000},
    "cuda_max_good": {"gte": 12.8},
    "disk_space": {"gte": DISK_GB},
    "verified": {"eq": True},
    "rentable": {"eq": True},
    "reliability": {"gte": 0.99},
    "direct_port_count": {"gte": 1},
    "geolocation": {"notin": ["CN"]},  # Hugging Face is not reachable from mainland China
}


def fail(message: str):
    sys.exit(f"ERROR: {message}")


def cheapest_offer(offers: list[dict], max_price: float) -> dict:
    if not offers:
        fail("no matching RTX 5090 offer found")
    offer = min(offers, key=lambda o: o["dph_total"])
    if offer["dph_total"] > max_price:
        fail(f"cheapest offer costs {offer['dph_total']:.3f} $/h, above --max-price {max_price}")
    return offer


def ssh_endpoint(instance: dict) -> tuple[str, int] | None:
    """Direct SSH port if the host has one, otherwise vast.ai's SSH proxy."""
    direct = (instance.get("ports") or {}).get("22/tcp")
    if instance.get("public_ipaddr") and direct:
        return instance["public_ipaddr"].strip(), int(direct[0]["HostPort"])
    if instance.get("ssh_host") and instance.get("ssh_port"):
        return instance["ssh_host"], int(instance["ssh_port"])
    return None


def describe(instance: dict) -> str:
    return (
        f"instance {instance['id']}: {instance.get('gpu_name')}, {instance.get('geolocation')}, "
        f"{instance.get('dph_total', 0):.3f} $/h, status {instance.get('actual_status')}"
    )


def train_script(dataset: str, run: str, steps: int | None, resume: bool) -> str:
    """Shell script for the instance: BFL's LoRA recipe on a local dataset, or resuming a run."""
    for name in (dataset, run):
        if not re.fullmatch(r"[\w.-]+", name):
            fail(f"'{name}' may only contain letters, digits, '.', '_' and '-'")
    if resume:
        arguments = [
            f"--config_path=outputs/{run}/checkpoints/last/pretrained_model/train_config.json",
            "--resume=true",
        ]
    else:
        arguments = [
            "--config_path=examples/flux3/lora.json",
            "--policy.path=models/flux-3-action-so101",
            "--policy.device=cuda",
            "--policy.video_vae_id=models/flux-3-action-base/video_vae.safetensors",
            "--policy.text_encoder_id=models/flux-3-action-base/text_encoder",
            f"--dataset.repo_id=local/{dataset}",
            f"--dataset.root=/workspace/data/{dataset}",
            f"--output_dir=outputs/{run}",
        ]
        if steps is not None:
            arguments.append(f"--steps={steps}")
    lines = [
        "set -euo pipefail",
        "cd /workspace/lerobot",
        "source .venv/bin/activate",
        "export HF_HUB_OFFLINE=1  # everything needed is already on the disk",
        "python -m lerobot.scripts.lerobot_train \\",
        *[f"  {argument} \\" for argument in arguments[:-1]],
        f"  {arguments[-1]}",
    ]
    return "\n".join(lines) + "\n"


def api_health(port: int) -> dict | None:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as response:
            return json.load(response)
    except (OSError, ValueError):
        return None


class Deployment:
    def __init__(self):
        from dotenv import load_dotenv
        from vastai import VastAI

        load_dotenv(HERE / ".env")
        if not os.environ.get("VASTAI_API_KEY"):
            fail("VASTAI_API_KEY is missing; put it into cloud/.env")
        self.vast = VastAI(api_key=os.environ["VASTAI_API_KEY"], raw=True, quiet=True)
        self.key = Path(os.environ.get("SSH_KEY_PATH") or Path.home() / ".ssh" / "id_ed25519")
        self.host = self.port = None

    # --- vast.ai -----------------------------------------------------------------

    def instance(self) -> dict | None:
        mine = [i for i in self.vast.show_instances() if i.get("label") == LABEL]
        if len(mine) > 1:
            fail(f"several instances are labelled {LABEL}; clean up in the vast.ai console")
        return mine[0] if mine else None

    def rent(self, max_price: float) -> int:
        offers = self.vast.search_offers(
            query=OFFER_QUERY, type="on-demand", order="dph_total", limit=20, storage=DISK_GB
        )
        offer = cheapest_offer(offers, max_price)
        print(f"Renting offer {offer['id']}: {offer.get('geolocation')}, {offer['dph_total']:.3f} $/h")
        result = self.vast.create_instance(
            id=offer["id"], image=IMAGE, disk=DISK_GB, ssh=True, direct=True, label=LABEL
        )
        if not result.get("success"):
            fail(f"vast.ai rejected the rental: {result}")
        KNOWN_HOSTS.unlink(missing_ok=True)  # a new machine has a new host key
        return result["new_contract"]

    def wait_running(self, instance_id: int) -> dict:
        print("Waiting for the instance to boot ...")
        started = False
        deadline = time.monotonic() + 15 * 60
        while time.monotonic() < deadline:
            instance = self.vast.show_instance(id=instance_id) or {}
            status = instance.get("actual_status")
            if status == "running" and ssh_endpoint(instance):
                return instance
            if status == "offline":
                fail(f"instance {instance_id} is offline; check the vast.ai console")
            if status in ("exited", "stopped") and not started:  # vast.ai reports a stopped one as exited
                print("Starting the stopped instance ...")
                self.vast.start_instance(id=instance_id)
                started = True
            time.sleep(10)
        fail(f"instance {instance_id} did not start within 15 minutes; it may still be billed")

    # --- ssh ---------------------------------------------------------------------

    def ssh_command(self, *extra: str) -> list[str]:
        return [
            "ssh",
            "-i", str(self.key),
            "-p", str(self.port),
            "-o", "BatchMode=yes",
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", f"UserKnownHostsFile={KNOWN_HOSTS.as_posix()}",
            "-o", "ServerAliveInterval=15",
            *extra,
            f"root@{self.host}",
        ]  # fmt: skip

    def ssh(self, command: str, stdin: bytes | None = None, check: bool = True, quiet: bool = False) -> int:
        """Run a command on the instance; its output goes straight to this terminal."""
        result = subprocess.run(
            [*self.ssh_command(), command],
            input=stdin,
            stdin=subprocess.DEVNULL if stdin is None else None,
            stdout=subprocess.DEVNULL if quiet else None,
            stderr=subprocess.DEVNULL if quiet else None,
        )
        if check and result.returncode:
            fail(f"remote command failed (exit {result.returncode}): {command}")
        return result.returncode

    def wait_ssh(self):
        print(f"Waiting for SSH on {self.host}:{self.port} ...")
        deadline = time.monotonic() + 5 * 60
        while self.ssh("true", check=False, quiet=True) != 0:
            if time.monotonic() > deadline:
                fail("SSH did not come up; is the key attached and free of a passphrase?")
            time.sleep(10)

    def upload(self, name: str):
        # Through stdin with Unix line endings, so a Windows checkout cannot break the shell script.
        content = (HERE / name).read_bytes().replace(b"\r\n", b"\n")
        self.ssh(f"mkdir -p /workspace && cat > /workspace/{name}", stdin=content)

    def upload_dir(self, local: Path, remote_parent: str):
        """Copy a directory to remote_parent/<its name> as a tar stream, replacing an older copy."""
        self.ssh(f"mkdir -p {remote_parent} && rm -rf {remote_parent}/{local.name}")
        process = subprocess.Popen(
            [*self.ssh_command(), f"tar -xf - -C {remote_parent}"], stdin=subprocess.PIPE
        )
        with tarfile.open(fileobj=process.stdin, mode="w|") as tar:
            tar.add(local, arcname=local.name)
        process.stdin.close()
        if process.wait():
            fail(f"upload of {local} failed")

    def download(self, remote_dir: str, names: str, local: Path):
        """Copy entries of a remote directory as a tar stream, following symlinks."""
        process = subprocess.Popen(
            [*self.ssh_command(), f"cd {remote_dir} && tar -chf - {names}"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
        )
        local.mkdir(parents=True, exist_ok=True)
        with tarfile.open(fileobj=process.stdout, mode="r|") as tar:
            tar.extractall(local, filter="data")
        if process.wait():
            fail(f"download from {remote_dir} failed")

    # --- commands ----------------------------------------------------------------

    def connect(self, max_price: float | None) -> dict:
        """Find our instance (or rent one if max_price is given) and wait until SSH works."""
        if not self.key.is_file() or not self.key.with_name(self.key.name + ".pub").is_file():
            fail(f"SSH key pair {self.key} not found; create one with ssh-keygen or set SSH_KEY_PATH")
        instance = self.instance()
        if instance:
            print(f"Using {describe(instance)}")
        elif max_price is None:
            fail(f"no instance labelled {LABEL}; nothing to connect to")
        instance_id = instance["id"] if instance else self.rent(max_price)
        try:
            instance = self.wait_running(instance_id)
            public_key = self.key.with_name(self.key.name + ".pub").read_text().strip()
            try:  # the account's key is not copied to SDK-created instances
                self.vast.attach_ssh(instance_id=instance_id, ssh_key=public_key)
            except Exception as exc:
                print(f"attach_ssh: {exc} (ignored, the key may already be attached)")
            self.host, self.port = ssh_endpoint(instance)
            self.wait_ssh()
        except BaseException:
            print(f"\nInstance {instance_id} may be running and billed. Run `deploy.py down` to stop it.")
            raise
        return instance

    def setup(self, environment: str = ""):
        """Install LeRobot and the model as in BFL's guide; `environment` goes in front of the script."""
        hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ACCESS_TOKEN")
        if not hf_token:
            fail("HF_TOKEN is missing; put it into cloud/.env")
        self.upload("server.py")
        self.upload("setup_remote.sh")
        # The token is piped through stdin so it never shows up in a command line.
        self.ssh(
            f"read -r HF_TOKEN && export HF_TOKEN && {environment} bash /workspace/setup_remote.sh",
            stdin=hf_token.encode() + b"\n",
        )

    def up(self, max_price: float, local_port: int, redeploy: bool, adapter: Path | None):
        if adapter is not None and not (adapter / "adapter_config.json").is_file():
            fail(f"{adapter} is not an adapter directory (no adapter_config.json)")
        if adapter is not None and not re.fullmatch(r"[\w.-]+", adapter.name):
            fail(f"adapter directory name '{adapter.name}' may only contain letters, digits, '.', '_', '-'")
        instance = self.connect(max_price)
        try:
            self.serve(instance, local_port, redeploy, adapter)
        except BaseException:
            print(
                f"\nInstance {instance['id']} is still running and billed. Run `deploy.py down` to stop it."
            )
            raise

    def serve(self, instance: dict, local_port: int, redeploy: bool, adapter: Path | None):
        if self.ssh("tmux has-session -t train", check=False, quiet=True) == 0:
            fail(
                "a training runs on the instance; the server would take its GPU memory. See `deploy.py logs`."
            )
        running = self.ssh("curl -fs http://127.0.0.1:8000/health", check=False, quiet=True) == 0
        if adapter is not None:
            self.upload_dir(adapter, "/workspace/adapters")
            self.setup(f"SERVER_ARGS='--adapter /workspace/adapters/{adapter.name}'")
        elif running and not redeploy:
            print("Server already runs on the instance; skipping setup (use --redeploy to redo it).")
        else:
            self.setup()

        print(f"Opening tunnel 127.0.0.1:{local_port} -> instance, waiting for the model (about 2 min) ...")
        tunnel = subprocess.Popen(
            [*self.ssh_command("-N", "-L", f"{local_port}:127.0.0.1:8000")], stdin=subprocess.DEVNULL
        )
        try:
            deadline = time.monotonic() + 15 * 60
            while (health := api_health(local_port) or {}).get("status") != "ready":
                if health.get("status") == "error":
                    fail(f"model failed to load: {health['error']} (see /workspace/server.log)")
                if tunnel.poll() is not None:
                    fail(f"SSH tunnel exited; is local port {local_port} already in use?")
                if time.monotonic() > deadline:
                    fail("model did not become ready; see /workspace/server.log on the instance")
                time.sleep(5)
            print(f"\nREADY on {health['model']} ({describe(instance)})")
            print(f"API: http://127.0.0.1:{local_port}  (docs: /docs, health: /health)")
            print("Ctrl+C closes the tunnel only. Stop the billing with: uv run cloud/deploy.py down")
            tunnel.wait()
            print("SSH tunnel ended. The instance is STILL RUNNING; rerun `up` or stop it with `down`.")
        except KeyboardInterrupt:
            print("\nTunnel closed. The instance is STILL RUNNING; run `deploy.py down` to stop it.")
        finally:
            tunnel.terminate()

    def train(self, max_price: float, dataset: Path, run: str, steps: int | None, resume: bool):
        if not (dataset / "meta" / "info.json").is_file():
            fail(f"{dataset} is not a LeRobot dataset (no meta/info.json)")
        script = train_script(dataset.name, run, steps, resume)
        instance = self.connect(max_price)
        try:
            if self.ssh("tmux has-session -t train", check=False, quiet=True) == 0:
                fail("a training already runs on the instance; watch it with `deploy.py logs`")
            self.setup("START_SERVER=0")  # the server would occupy GPU memory the training needs
            exists = self.ssh(f"test -e /workspace/lerobot/outputs/{run}", check=False, quiet=True) == 0
            if exists != resume:
                fail(
                    f"run '{run}' already exists on the instance; add --resume or choose another --run"
                    if exists
                    else f"run '{run}' does not exist on the instance, nothing to resume"
                )
            print(f"Uploading {dataset} ...")
            self.upload_dir(dataset, "/workspace/data")
            self.ssh("cat > /workspace/train.sh", stdin=script.encode())
            self.ssh("tmux new-session -d -s train 'bash /workspace/train.sh > /workspace/train.log 2>&1'")
        except BaseException:
            print(
                f"\nInstance {instance['id']} is still running and billed. Run `deploy.py down` to stop it."
            )
            raise
        print(f"\nTraining '{run}' started on {describe(instance)}.")
        print("It keeps running without this terminal. Watch it with: uv run cloud/deploy.py logs")
        print("When it is done: `deploy.py fetch`, then `deploy.py down`. The instance is billed until then.")

    def logs(self):
        self.connect(None)
        running = self.ssh("tmux has-session -t train", check=False, quiet=True) == 0
        print("Training is running." if running else "No training is running; this is the last log.")
        self.ssh("nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv", check=False)
        try:  # follow the log while the training runs, otherwise just show its end
            self.ssh(f"tail -n 40 {'-f' if running else ''} /workspace/train.log", check=False)
        except KeyboardInterrupt:
            print("\nStopped watching. The training continues on the instance.")

    def fetch(self, run: str, out: Path):
        self.connect(None)
        last = f"/workspace/lerobot/outputs/{run}/checkpoints/last"
        if self.ssh(f"test -d {last}/pretrained_model", check=False, quiet=True) != 0:
            fail(f"run '{run}' has no saved checkpoint yet (it saves every 500 steps and at the end)")
        self.ssh(f"du -shL {last}/pretrained_model*")
        self.download(last, "pretrained_model*", out)
        print(
            f"Saved to {out}. Serve it with: uv run cloud/deploy.py up --adapter {out / 'pretrained_model'}"
        )

    def down(self, destroy: bool):
        instance = self.instance()
        if not instance:
            print(f"No instance labelled {LABEL}.")
        elif destroy:
            self.vast.destroy_instance(id=instance["id"])
            print(f"Destroyed instance {instance['id']} including its disk.")
        else:
            self.vast.stop_instance(id=instance["id"])
            print(f"Stopped instance {instance['id']}. Only its disk is billed now; `up` starts it again.")

    def status(self, local_port: int):
        instance = self.instance()
        print(describe(instance) if instance else f"No instance labelled {LABEL}.")
        print(f"API on 127.0.0.1:{local_port}: {api_health(local_port) or 'not reachable'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("command", choices=["up", "status", "down", "train", "logs", "fetch"])
    parser.add_argument("--max-price", type=float, default=1.0, help="rental limit in $/h (default 1.0)")
    parser.add_argument("--port", type=int, default=8000, help="local tunnel port (default 8000)")
    parser.add_argument("--redeploy", action="store_true", help="re-upload server.py and rerun the setup")
    parser.add_argument("--destroy", action="store_true", help="with down: delete the instance and its disk")
    parser.add_argument("--adapter", type=Path, help="with up: local adapter directory to serve")
    parser.add_argument("--dataset", type=Path, help="with train: local LeRobot dataset directory")
    parser.add_argument("--run", default="nexarm_lora", help="training run name (default nexarm_lora)")
    parser.add_argument("--steps", type=int, help="with train: microsteps instead of the recipe's 10000")
    parser.add_argument("--resume", action="store_true", help="with train: continue an existing run")
    parser.add_argument("--out", type=Path, help="with fetch: target (default outputs/lora/<run>)")
    args = parser.parse_args()
    if args.command == "train" and args.dataset is None:
        parser.error("train needs --dataset")
    deployment = Deployment()
    if args.command == "up":
        deployment.up(args.max_price, args.port, args.redeploy, args.adapter)
    elif args.command == "train":
        deployment.train(args.max_price, args.dataset, args.run, args.steps, args.resume)
    elif args.command == "logs":
        deployment.logs()
    elif args.command == "fetch":
        deployment.fetch(args.run, args.out or Path("outputs") / "lora" / args.run)
    elif args.command == "down":
        deployment.down(args.destroy)
    else:
        deployment.status(args.port)


if __name__ == "__main__":
    main()
