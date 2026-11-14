# Cloud-Inferenz: FLUX 3 Action auf einer gemieteten RTX 5090

Ein Befehl mietet die günstigste passende RTX 5090 auf vast.ai, installiert LeRobot mit
FLUX 3 Action, lädt das SO-101-Modell und stellt eine HTTP-API auf dem Laptop bereit.

| Datei | Läuft auf | Aufgabe |
| --- | --- | --- |
| `deploy.py` | Laptop | Instanz mieten, einrichten, Tunnel öffnen, stoppen |
| `setup_remote.sh` | Instanz | Installation und Modell-Download nach der BFL-Anleitung, Serverstart |
| `server.py` | Instanz | FastAPI-Server mit `/health` und `/predict` |

## Einmalig vorbereiten

1. `cloud/.env.example` nach `cloud/.env` kopieren und `VASTAI_API_KEY` sowie `HF_TOKEN`
   eintragen. Der Hugging-Face-Account braucht die Freigabe für **beide** Repos:
   `black-forest-labs/flux-3-action-so101` und `black-forest-labs/flux-3-action-base`.
2. Ein SSH-Schlüssel ohne Passphrase unter `~/.ssh/id_ed25519` (sonst `SSH_KEY_PATH` setzen).
   Neu anlegen: `ssh-keygen -t ed25519`.
3. Guthaben auf dem vast.ai-Account.

## Starten

```powershell
cd C:\Users\mario\robot\lerobot-nexarm
uv run cloud/deploy.py up
```

Das kostet Geld. Ablauf:

1. Günstigstes Angebot suchen (1× RTX 5090, 120 GB Disk, verifiziert, nicht in China) und
   mieten. Liegt der Preis über `--max-price` (Standard 1 $/h), bricht das Skript vorher ab.
2. Auf die Instanz warten, SSH-Schlüssel anhängen.
3. `setup_remote.sh` ausführen: LeRobot am Projekt-Pin, Torch 2.11 (cu128), NATTEN, ffmpeg,
   dann `hf download` beider Pakete (ca. 25 GB) und Serverstart in tmux.
4. SSH-Tunnel öffnen und warten, bis das Modell geladen ist.

Danach steht `READY` im Terminal und die API ist unter <http://127.0.0.1:8000> erreichbar
(`/docs` zeigt das Schema). Der erste Lauf dauert etwa 20 bis 30 Minuten, vor allem wegen
des Downloads.

`Strg+C` schließt nur den Tunnel. **Die Instanz läuft und kostet weiter**, bis:

```powershell
uv run cloud/deploy.py down            # stoppen, Disk bleibt (kleine Lagerkosten)
uv run cloud/deploy.py down --destroy  # löschen, auch Modell und Umgebung
```

Ein erneutes `up` verwendet die vorhandene Instanz (erkannt am Label `nexarm-f3a`) und
überspringt die Einrichtung, wenn der Server schon läuft. Nach Änderungen an `server.py`:
`uv run cloud/deploy.py up --redeploy`. Zustand prüfen: `uv run cloud/deploy.py status`.

## API

`POST /predict`

```json
{
  "task": "put the blue block into the bowl",
  "frames": [
    {
      "image_scene": "<base64 JPEG>",
      "image_wrist": "<base64 JPEG>",
      "state": [0, 0, 0, 0, 0, 50],
      "last_command": null
    }
  ]
}
```

- `frames`: älteste zuerst, neueste zuletzt. Der Checkpoint erwartet 8 Zeitschritte. Sind es
  weniger (Episodenbeginn), wird der älteste Frame vorne wiederholt.
- `state` und `last_command`: fünf Armgelenke in Grad, Greifer 0 bis 100, in der Reihenfolge
  des Plugins. `last_command` ist der Befehl, der direkt vor diesem Frame an den Arm ging;
  `null` am Episodenbeginn.
- Antwort: `commands` mit 32 absoluten Befehlen in denselben Einheiten und `seconds`.

Der Server merkt sich nichts zwischen zwei Anfragen. Er setzt Policy und Prozessoren bei
jeder Anfrage zurück.

## Arm steuern: `client.py`

Der Client läuft auf dem Laptop in der Plugin-Umgebung. Er beobachtet Arm und Kameras,
holt 32 Befehle vom Server, prüft den ersten und führt sie mit 30 Hz aus. Dabei schreibt
er jeden Takt mit und schickt beim nächsten Plan die letzten acht als Historie. Während
der Server rechnet, sendet er nichts und der Arm hält seine Position.

```powershell
# 1. Ohne Arm und ohne Kameras: testet Server und Tunnel
uv run python cloud/client.py --task "put the blue block into the bowl" --fake-robot

# 2. Mit Arm, aber ohne Bewegung (Dry-run ist Standard)
uv run python cloud/client.py --task "put the blue block into the bowl" --config examples/nexarm/inference.yaml

# 3. Mit Bewegung
uv run python cloud/client.py --task "put the blue block into the bowl" --config examples/nexarm/inference.yaml --execute
```

- **Dry-run:** Ohne `--execute` geht kein Befehl an den Arm. Der Follower wird trotzdem
  verbunden und hält mit eingeschaltetem Drehmoment seine Position.
- **Kalibrierung:** Mit `--config` bricht der Client vor dem Verbinden ab, wenn keine
  gültige Follower-Kalibrierung vorliegt.
- **Kameras:** Die YAML muss `scene` (feste Außenkamera) und `wrist` definieren.
- **Sprungprüfung:** Liegt der erste Befehl eines Plans mehr als 15° (Greifer 30) vom
  gemessenen Zustand entfernt, wird der Plan verworfen und die Schleife endet
  (`--arm-jump`, `--gripper-jump`).
- **Timeout:** Antwortet der Server nicht innerhalb von 5 s (`--timeout`), endet die Schleife.
- **Ende:** nach `--duration` Sekunden (Standard 30) oder mit `Strg+C`. Der Arm hält danach
  weiter seine Position.
- **Log:** eine Zeile pro Plan in `outputs/cloud_client.jsonl` (Latenz, Zustand, erster und
  letzter Befehl).

Vor dem ersten `--execute`: Koordinatenlimits in der Hiwonder-Software setzen, freien
Arbeitsbereich schaffen und eine Person an den Netzschalter stellen.

## Ohne Arm: simulierter NexArm in MuJoCo

`--sim` ersetzt den Arm durch ein MuJoCo-Modell. Der Client bekommt gerenderte Bilder der
Szenen- und Handkamera und Gelenkwerte aus der Physik; auf dem Tisch stehen eine kleine und
eine große Box. Das Armmodell stammt aus einem fremden Repo und wird nicht mit eingecheckt:

```powershell
git clone --depth 1 https://github.com/khanhthanhdev/lerobot-nexarm.git third_party/khanhthanhdev-lerobot-nexarm
git -C third_party/khanhthanhdev-lerobot-nexarm lfs pull --include "sim/assets/**"

uv run --with mujoco python cloud/client.py --task "put the small box on top of the big box" `
  --sim third_party/khanhthanhdev-lerobot-nexarm/sim/description/mjcf/scene.xml `
  --video outputs/sim.mp4 --execute
```

- Die Simulation prüft die Schleife, die Sicherheitslogik und grob die Bewegungsrichtungen.
  Ob das Modell die Aufgabe am echten Arm löst, zeigt sie nicht.
- Die Einheiten entsprechen der Kalibrierung der Aufnahmen vom 13.11.: 0° ist Hiwonders
  Grundstellung, Greifer 0 ist offen und 100 geschlossen. Geprüft durch Nachspielen einer
  echten Episode; die Richtungen von `shoulder_pan` und `wrist_roll` sind ungeprüft.
- Die Simulation läuft langsamer als Echtzeit (auf dem Laptop etwa 18 Takte pro Sekunde).
  Die simulierte Zeit stimmt trotzdem: Jeder Takt rechnet 1/30 s Physik.
- Mit `--execute` bewegt sich nur der simulierte Arm.

Ohne GPU eine Bewegung sehen: `uv run cloud/server.py --mock-sweep --port 8011` starten und
den Client mit `--url http://127.0.0.1:8011` aufrufen. Dieser Mock fährt langsam zwischen
zwei Stellungen hin und her. Er ist nur für die Simulation gedacht; mit dem echten Arm und
`--execute` würde er den Arm bewegen.

## Lokal ohne GPU testen

```powershell
uv run cloud/server.py --mock
```

Der Mock lädt kein Modell und gibt den gemessenen Zustand 32-mal zurück. Tests:

```powershell
uv run --with fastapi --with httpx pytest tests/test_cloud.py
```

## Wenn etwas hängt

- Log auf der Instanz: `/workspace/server.log`. Die tmux-Sitzung heißt `f3a`.
- `model failed to load`: meistens fehlt die HF-Freigabe für eines der beiden Repos.
- `SSH did not come up`: Schlüssel mit Passphrase oder falscher `SSH_KEY_PATH`.
- Port 8000 lokal belegt (z. B. vom Mock): `--port 8001`.
