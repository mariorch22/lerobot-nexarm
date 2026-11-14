#!/usr/bin/env bash
# Runs on the rented GPU instance. Installs LeRobot with FLUX 3 Action exactly as in
# BFL's "SO-101 with LeRobot" guide, downloads the model and starts the server.
# Safe to run again: finished steps are skipped or are quick no-ops.
# Expects HF_TOKEN in the environment (read access to both gated F3A repos).
set -euo pipefail

LEROBOT_COMMIT=2f05d8f64d62a865c368a9fdf0ba3d8423e28035   # same pin as the NexArm plugin
POLICY_REVISION=c9e13b2aca6a0a472b3ea03fd90cff32d3e85849
ENCODER_REVISION=62878e2925e59b7a89ec14463ce89932624c490d

export DEBIAN_FRONTEND=noninteractive
export PATH="$HOME/.local/bin:$PATH"
export GIT_LFS_SKIP_SMUDGE=1   # upstream test images are not needed

echo "== system packages"
apt-get update -qq
apt-get install -y -qq git ffmpeg curl tmux
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh

echo "== LeRobot at $LEROBOT_COMMIT"
mkdir -p /workspace/lerobot
cd /workspace/lerobot
# Fetch only the pinned commit: quick, and it repairs a checkout that was interrupted earlier.
if [ "$(git rev-parse HEAD 2>/dev/null)" != "$LEROBOT_COMMIT" ]; then
  git init -q
  git fetch --progress --depth 1 https://github.com/huggingface/lerobot.git "$LEROBOT_COMMIT"
  git checkout -q FETCH_HEAD
fi
[ -d .venv ] || uv venv --python 3.12
source .venv/bin/activate
uv pip install 'torch==2.11.0' 'torchvision==0.26.0' \
  --index-url https://download.pytorch.org/whl/cu128
uv pip install -e '.[training,flux3,peft,diffusion]'
uv pip install 'natten==0.21.6+torch2110cu128' --find-links https://whl.natten.org/
uv pip install fastapi uvicorn pillow   # only needed by our server
ffmpeg -version | head -n 1
python -c 'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))'

echo "== model download (about 25 GB on the first run)"
hf download black-forest-labs/flux-3-action-so101 \
  --revision "$POLICY_REVISION" \
  --local-dir models/flux-3-action-so101
hf download black-forest-labs/flux-3-action-base \
  --revision "$ENCODER_REVISION" \
  --include 'video_vae.safetensors' --include 'text_encoder/*' \
  --local-dir models/flux-3-action-base
python - <<'EOF'
import json
config = json.load(open("models/flux-3-action-so101/config.json"))
for key in ("camera_keys", "camera_layout", "fps", "chunk_size", "n_action_steps", "n_obs_steps"):
    print(key, config.get(key))
assert config["fps"] == 30
EOF

tmux kill-session -t f3a 2>/dev/null || true
if [ "${START_SERVER:-1}" != 1 ]; then
  echo "== setup done (server not started)"
  exit 0
fi
echo "== start server in tmux session 'f3a' (log: /workspace/server.log)"
# The server only reads local files; it does not get the HF token.
tmux new-session -d -s f3a \
  "env -u HF_TOKEN HF_HUB_OFFLINE=1 /workspace/lerobot/.venv/bin/python /workspace/server.py ${SERVER_ARGS:-} > /workspace/server.log 2>&1"
echo "== setup done"