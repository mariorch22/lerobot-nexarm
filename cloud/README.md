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
