# lerobot-nexarm

Standalone-LeRobot-Plugin für den Hiwonder NexArm mit HX-30HM-Servos:
CommProtocol-Motorbus, `nexarm_follower` und `nexarm_leader`. Upstream-LeRobot
bleibt unverändert. Ziel ist ausschließlich Commit
`2f05d8f64d62a865c368a9fdf0ba3d8423e28035`.

Der Python-Distributionsname ist **`lerobot_robot_nexarm`**: Dieses Präfix benötigt
die Plugin-Erkennung am Pin. Ein Import registriert beide Gerätetypen.
Die Hardware wurde von diesem Agenten weder verbunden noch bewegt; die automatische
Prüfung arbeitet ausschließlich mit Serial-/Kamera-Mocks.
Quellenvergleich, Entscheidungen und Grenzen stehen in [PORTING_NOTES.md](PORTING_NOTES.md).

## Installation unter Windows mit uv und Python 3.12

PowerShell im vorhandenen Repo `lerobot-nexarm`:

```powershell
uv venv --python 3.12
# Für den Paketbau werden die Upstream-LFS-Testbilder nicht benötigt.
$env:GIT_LFS_SKIP_SMUDGE = "1"
uv pip install "lerobot[core_scripts] @ git+https://github.com/huggingface/lerobot.git@2f05d8f64d62a865c368a9fdf0ba3d8423e28035"
uv pip install -e .
# Entwicklerabhängigkeiten und reproduzierbare Umgebung:
uv sync --locked
uv run pytest
```

Eine Aktivierung ist mit `uv run` nicht nötig. Optional:
`.\.venv\Scripts\Activate.ps1`. Weder `hiwonder-fork` noch `old/finsh` zusätzlich
in diese Umgebung installieren: Beide verwenden denselben Importnamen `lerobot`.
`core_scripts` stellt die Abhängigkeiten für die Standard-CLIs bereit.

Auf dem späteren GPU-Server ergänzt `uv sync --locked --extra cloud` das
Upstream-Extra `flux3` **am selben Git-Commit**. Das Plugin lädt selbst keine Modelle.

## Ports und Kameras bestimmen

Diese Befehle führen Menschen bei der Hardwareeinrichtung aus:

```powershell
uv run lerobot-find-port
uv run lerobot-find-cameras opencv
```

Follower `COM19`, Leader `COM18` und Kameraindizes `1`/`2` in den Beispielen sind
Platzhalter. `lerobot-find-port` ist ein allgemeines Enumerationstool ohne
`--robot.type`. Während des Betriebs dürfen Hiwonders PC-Tool und serielle Monitore
den betreffenden Port nicht gleichzeitig belegen.

Die Beispiele konfigurieren `front` und `wrist` mit 640×480 bei 30 fps und `MJPG`.
`fourcc`, Indizes und Namen sind frei konfigurierbar; nach einer Namensänderung auch
Dataset-/Policy-Zuordnung prüfen. Für den untersuchten F3A-SO-101-Checkpoint heißt
die Außenkamera `scene`; das Inferenzbeispiel bildet `front` über `rename_map` darauf ab.

## Kalibrieren: erst Follower, dann Leader

**Die folgenden Kommandos öffnen echte Geräte. Sie sind für die menschliche
Hardwareabnahme bestimmt.** Den Arm beim Abschalten des Drehmoments mechanisch
stützen. Die Kalibrierung bleibt durchgehend torque off.

```powershell
uv run lerobot-calibrate --robot.type=nexarm_follower --robot.port=COM19 --robot.id=follower --robot.calibration_dir=calibration/follower
uv run lerobot-calibrate --teleop.type=nexarm_leader --teleop.port=COM18 --teleop.id=leader --teleop.calibration_dir=calibration/leader --teleop.follower_calibration_path=calibration/follower/follower.json
```

Die interaktive Routine:

1. Arm in die SO-101-Mittel-/Referenzpose bringen und ENTER drücken. Die sechs
   Rohpositionen werden als hostseitige Nullpunkte `homing_offset` gespeichert.
   Die Pose ist am realen Arm abzugleichen; es werden keine Servo-Offsets geschrieben.
2. Nacheinander jedes Gelenk langsam durch seinen benutzbaren Bereich bewegen.
   ENTER startet bzw. beendet die Aufnahme pro Gelenk. Alle sechs Achsen werden
   während der Aufnahme überwacht, kein Gelenk wird automatisch gefahren.
3. Ein Sprung um mehr als 2048 Ticks zwischen Abtastungen wird als möglicher
   Encoderübergang `4095↔0` behandelt: Abbruch mit Fehlermeldung statt Wrap-Korrektur.
   Auch zu schnelle Bewegungen können diesen konservativen Abbruch auslösen.
4. Gespeicherte Datei prüfen und Richtungen manuell setzen. Torque bleibt aus;
   vor Steuerung müssen beide Geräte getrennt und neu verbunden werden.

Die Beispiele verwenden `calibration/follower/follower.json` und
`calibration/leader/leader.json` relativ zum Arbeitsverzeichnis. Ohne
`calibration_dir` gelten die Standardpfade von LeRobot:
`HF_LEROBOT_CALIBRATION/robots/nexarm_follower/<id>.json` bzw.
`HF_LEROBOT_CALIBRATION/teleoperators/nexarm_leader/<id>.json`.
Standardbasis ist `HF_HOME/lerobot/calibration`; Umgebungs-Overrides werden beachtet.

Jeder der sechs Einträge enthält `id`, `drive_mode`, `homing_offset`, `range_min`
und `range_max`. **`drive_mode: 0` bedeutet Vorzeichen +1, `1` bedeutet −1.**
Für den Greifer kehrt `1` die Prozentskala mit `100-v` um. Welche Seite offen ist,
messen Menschen am Arm; es gibt dafür keine angenommene Voreinstellung.
Der Follower-Greiferbereich muss innerhalb `[1195, 2833]` liegen.

Der Leader referenziert mit **`follower_calibration_path` dieselbe Datei wie der
Follower**. Seine Rohwerte durchlaufen zuerst die unveränderte Schulterspiegelung
`4096-pos` und die Greiferformel `2833+(pos-2048)*4`. Erst danach erfolgen
Begrenzung und Normierung mit der Follower-Kalibrierung. Die Richtungen der
Leader-eigenen Messdatei werden nicht zusätzlich auf Teleop-Aktionen angewendet.
Bei Richtungsänderungen die Follower-Datei bearbeiten und **beide Geräte neu starten**.

Unvollständige/ungültige Kalibrierungen und die alte pauschale Signatur
(alle Achsen `0..4095`, Offset `2048`, `drive_mode=0`) werden verworfen.
Ohne gültige Kalibrierung werden keine Aktionen gesendet. Auch nach einer
automatischen Erstkalibrierung ist ein Reconnect nötig. Bei Abbruch wird Torque
abgeschaltet, die Follower-Bridge verlassen und die bisherige Datei beibehalten.

## Einheiten und F3A-Vertrag

Default ist **Grad für die fünf Armgelenke, `[0,100]` für den Greifer**.
Die [SO-101-Modellkarte](https://huggingface.co/black-forest-labs/flux-3-action-so101#calibration-and-normalization)
bestätigt diese Einheiten. Geprüfte Checkpoint-Revision:
`e2584b2698e3b88368854976e354af87ec9893c6`.
Die sieben Config-/Normalizer-Dateien wurden ohne Modellgewichte heruntergeladen;
[Prüfbericht mit Hashes und Quantilen](reference/contract_report.json).

Die Gradumrechnung ist `sign*(raw-homing_offset)*360/4095`. Der gemessene
Referenznullpunkt, Software-Vorzeichen, `round()` auf dem Rückweg und Begrenzung
auf die kalibrierten Rohgrenzen sind bewusste NexArm-Erweiterungen gegenüber dem
gepinnten SO-Treiber. Diese Einheiten alleine garantieren keine geometrische
Übertragbarkeit eines SO-101-Checkpoints auf NexArm.

`use_degrees: false` unterstützt alternativ `[-100,100]` für die Armachsen,
mit Mittelpunkt des gemessenen Bereichs. Für den geprüften Checkpoint **true lassen**;
Leader und Follower müssen denselben Modus verwenden. Die F3A-Prozessoren übernehmen
ihre eigene Modellnormalisierung und Delta-Integration. Sie dürfen keine
unveränderten NexArm-Encoderwerte als Eingabe erhalten. Das Plugin gibt bereits
Hardwarewerte in Grad/Prozent an LeRobot und an aufgezeichnete Datasets weiter.

## Teleoperation und Recording

Zuerst Ports/Indizes anpassen, beide Kalibrierungen durchführen und Richtungen
am Arm prüfen. Die Beispiele verwenden denselben Kalibrierungspfad wie oben.

```powershell
uv run lerobot-teleoperate --config_path=examples/nexarm/teleoperate.yaml
uv run lerobot-record --config_path=examples/nexarm/record.yaml
```

Das Recording-Beispiel zeichnet zunächst zehn Episoden lokal auf. Dataset-Name,
Aufgabe und Zeitparameter anpassen; anschließend Episoden im Dataset-Visualizer prüfen.
`send_action()` gibt die normierten, gerundeten und begrenzten **gesendeten Ziele**
zurück, die LeRobot als Aktionen speichert. Messwerte bleiben Beobachtungen.
`readback_after_write: true` erhält den zusätzlichen CMD-96-Read nach CMD 97.
Erst nach menschlicher Timing-Prüfung optional auf `false` setzen.

Das Inferenzbeispiel benötigt einen zur eigenen Einrichtung passenden Checkpoint:

```powershell
uv run lerobot-rollout --config_path=examples/nexarm/inference.yaml --policy.path=YOUR_ADAPTED_CHECKPOINT
```

Es setzt `return_to_initial_position: false`; das Plugin meldet keine Hold-Fähigkeit.
F3A-Anpassung und Policy-Server sind nicht Bestandteil dieses Pakets.

## Troubleshooting

- **Follower bewegt sich nicht:** Port/Rolle prüfen. Der Treiber sendet beim
  Connect CMD 68 mit `1`, beim Disconnect mit `0`; die Firmware muss den
  LeRobot-Bridge-Modus unterstützen. Ohne gültige Kalibrierung oder nach einer
  Kalibrierung vor dem Reconnect sind Aktionen absichtlich gesperrt.
- **Drehmoment beim Trennen:** Herstellerdefault
  `disable_torque_on_disconnect: false` bleibt erhalten. Die Disconnect-Sequenz
  sendet damit im normalen Betrieb kein Torque-off; das tatsächliche Verhalten
  der Firmware nach Verlassen der Bridge müssen Menschen prüfen. Kalibrierung,
  Abbruch und fehlgeschlagenes Connect schalten Torque unabhängig davon aus.
- **Leader-Timeout / Checksum:** Der bekannte Firmwarefehler verlangt Akzeptanz
  sowohl der vollständigen als auch der kurzen Prüfsumme. Diese Toleranz bleibt
  unverändert. Debugtext wird übersprungen; Positionslesen versucht dreimal.
- **Port busy:** Hiwonder-Tool, Arduino-Monitor und andere LeRobot-Prozesse schließen.
- **Kamerabilder veraltet:** Der Windows-Fallback wartet per `async_read` auf ein
  neues Bild. Andere Kameraprogramme schließen und Indizes/`fourcc` prüfen.
- **WSL:** Serielle USB-Geräte erst mit usbipd an WSL anbinden. USB-Kameras unter
  WSL sind unzuverlässig; die Beispiele zielen auf natives Windows mit COM-Ports.
- **Plugin fehlt:** Installation in derselben Umgebung wie die CLI prüfen.
  `Name: lerobot_robot_nexarm` in den Distributionsmetadaten ist am Pin erforderlich;
  allein ein beliebig benanntes Modul auf `PYTHONPATH` genügt nicht.

## Tests und Pin-Bump

```powershell
uv run pytest
uv run ruff check src tests scripts
uv run ruff format --check src tests scripts
```

Die Tests verbieten echte `serial.Serial`-Aufrufe und ersetzen den Transport
durch Byte-Stream-Mocks. Discovery läuft zusätzlich in einem frischen Prozess;
Beispiele werden gegen die tatsächlichen CLI-Dataclasses geprüft.

Beim Bump den neuen Upstream-Commit gezielt auswählen und **beide** Git-Referenzen
in `pyproject.toml` gemeinsam ändern. Discovery, Basisklassen, Kalibrierungsformat,
Motor-Einheiten, Kamera-/Prozessor-APIs und Beispielschemata erneut vergleichen.
`uv lock`, Installation und Tests neu durchführen; Checkpointrevision und Statistiken
separat prüfen. Entscheidungen in `PORTING_NOTES.md` ergänzen. Erst danach folgt
erneut die menschliche Abnahme: torque-off-Positionsvergleich mit Hiwonder-Tool,
Kalibrierung/Vorzeichen, Teleoperation, zehn Episoden und Dataset-Visualizer.
