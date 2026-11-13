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

Die Beispiele verwenden die aktuell vom Nutzer zugeordneten Ports: Follower
`COM13`, Leader `COM14`. Für andere Anschlüsse erneut bestimmen; Kameraindizes
`1`/`2` sind Platzhalter. `lerobot-find-port` ist ein allgemeines Enumerationstool ohne
`--robot.type`. Während des Betriebs dürfen Hiwonders PC-Tool und serielle Monitore
den betreffenden Port nicht gleichzeitig belegen.

Die Beispiele konfigurieren `front` und `wrist` mit 640×480 bei 30 fps und `MJPG`.
`fourcc`, Indizes und Namen sind frei konfigurierbar; nach einer Namensänderung auch
Dataset-/Policy-Zuordnung prüfen. Für den untersuchten F3A-SO-101-Checkpoint heißt
die Außenkamera `scene`; das Inferenzbeispiel bildet `front` über `rename_map` darauf ab.

## Direkt teleoperieren wie mit old, ohne Kalibrierdialog

Für den ersten Test mit dem Leader gibt es denselben Rohwert-Ablauf wie in old.
Im neuen Repo starten; die zuletzt zugeordneten Ports sind Follower COM13 und
Leader COM14:

```powershell
uv run --locked python scripts/teleoperate_raw.py --follower-port=COM13 --leader-port=COM14
```

**Der Aufruf kann den Arm bewegen.** Der Leader erhält Torque-off, der Follower
Bridge-on und Torque-on, genau wie im alten normalen Teleoperationsbetrieb.
Es werden zuerst Follower- und Leader-Positionen gelesen, dann die unveränderte
Schulterspiegelung und Greiferformel angewandt und Rohziele gesendet. Die zusätzliche
Positionsabfrage nach jedem Write bleibt erhalten. Ohne `--camera-config` werden
keine Kameras geöffnet. Keine Kalibrierungsdateien, kein Modell und keine
Aufzeichnung. Default sind 30 Hz;
optional etwa `--fps=20 --duration=10`. Strg+C beendet den Lauf, sendet den
Bridge-Ausgangsbefehl und schließt beide Ports. Wie bei old wird beim Trennen
kein zusätzlicher Torque-off-Befehl an den Follower geschickt.

Für denselben Rohwertbetrieb **mit Kameras und Livebildern in Rerun**:

```powershell
uv run --locked python scripts/teleoperate_raw.py --follower-port=COM13 --leader-port=COM14 --camera-config=examples/nexarm/teleoperate.yaml
```

Das Skript übernimmt den Kamera-Lesepfad aus dem Herstellerfork und verwendet
die aktuellen LeRobot-Kameras. Es liest ausschließlich `robot.cameras` aus der
[vorhandenen YAML](examples/nexarm/teleoperate.yaml): `front` auf Index 1 und
`wrist` auf Index 2, jeweils 640×480, 30 fps, MJPG. Indizes und Namen dort an den
Aufbau anpassen; Kameras mit `uv run lerobot-find-cameras opencv` bestimmen.
Die COM-Ports kommen weiterhin aus den beiden CLI-Argumenten. Kalibrierungsfelder,
`fps` und `display_data` der YAML werden für diesen Aufruf nicht übernommen.

Mit `--camera-config` öffnet sich standardmäßig der Rerun-Viewer mit Bildern
und Gelenk-Rohwerten in Encoder-Ticks. Die nötige Rerun-Abhängigkeit ist bereits
in `core_scripts` enthalten. Die Livebilder werden zur Entlastung der Anzeige
als JPEG (Qualität 80) mit Zeitstempel übertragen; das verändert die Kamera-
Einstellungen und die Motorwerte nicht. `--no-display-data` liest dieselben Kameras ohne
Viewer; `--display-data` zeigt auch ohne Kamera-Konfiguration die Rohpositionen.
Kamera-Warmup erfolgt vor dem Öffnen der Serial-Ports. Bei veralteten Bildern
bleibt der Windows-Fallback auf ein frisches Bild erhalten. Strg+C oder ein
Kamera-/Serial-Fehler schließt Ports, Kameras und Viewer. Auch dieser Aufruf
kann den Arm bewegen und benötigt keine abgeschlossene Kalibrierung.

Die **tatsächlich erreichte Teleoperationsrate** mit `--show-fps` anzeigen:

```powershell
uv run --locked python scripts/teleoperate_raw.py --follower-port=COM13 --leader-port=COM14 --camera-config=examples/nexarm/teleoperate.yaml --show-fps
```

Einmal pro Sekunde erscheint `Measured FPS` mit gemessenen Durchläufen pro
Sekunde. `loop` ist die mittlere Zeit einschließlich der FPS-Begrenzung,
`work` die Arbeitszeit ohne diese Wartepause; `target` ist der mit `--fps`
eingestellte Sollwert. Beim Beenden erscheint zusätzlich `Overall FPS`.
Die Messung umfasst Serial, Kameraabfrage und Rerun. Sie misst die komplette
Teleoperationsschleife, nicht die unabhängige Bildrate des Kamerasensors.
Messung und Begrenzung verwenden `perf_counter()`: Unter Python 3.12 auf
Windows ist `monotonic()` für die Messung einzelner 30-Hz-Durchläufe zu grob.
Für einen Vergleich kann die Anzeige mit `--no-display-data` ausgeschaltet
oder die Kamera-Konfiguration ganz weggelassen werden.

Olds angebliche Kalibrierung schrieb nur pauschal `0..4095`, Offset `2048` und
`drive_mode=0` für alle Achsen. Für reine Rohwert-Teleoperation ist diese Datei
nicht nötig. Das Skript legt deshalb keine Platzhalter an und verändert keine
vorhandene Kalibrierung. Vor dem ersten Positionsziel müssen beide Arme auf
Positionsabfragen antworten; ein Timeout wird mit Rolle und Port ausgegeben.
Ob die Torque-on-Startfolge den bisher beobachteten Positions-Timeout behebt, ist
noch am Arm zu prüfen.

Für den F3A-SO-101-Checkpoint braucht der normale Plugin-Betrieb dagegen
Gelenkwinkel und Greiferprozente in der passenden Referenz. Dafür sind die
gemessenen Nullpunkte, Bereiche und Vorzeichen notwendig. Die folgenden
Standard-CLI-Beispiele gelten für diesen normierten Betrieb.

## Kalibrieren: erst Follower, dann Leader

**Die folgenden Kommandos öffnen echte Geräte. Sie sind für die menschliche
Hardwareabnahme bestimmt.** Den Arm beim Abschalten des Drehmoments mechanisch
stützen. Die Kalibrierung bleibt durchgehend torque off.

```powershell
uv run lerobot-calibrate --robot.type=nexarm_follower --robot.port=COM13 --robot.id=follower --robot.calibration_dir=calibration/follower
uv run lerobot-calibrate --teleop.type=nexarm_leader --teleop.port=COM14 --teleop.id=leader --teleop.calibration_dir=calibration/leader --teleop.follower_calibration_path=calibration/follower/follower.json
```

Die interaktive Routine:

Jeden Shell-Befehl einzeln am `PS ...>`-Prompt starten. Während die Kalibrierung
auf ENTER wartet, keine weiteren `uv run ...`-Befehle einfügen: Das ist ein
Programmeingabedialog. Strg+C bricht ab; dabei wird keine neue Kalibrierung gespeichert.
Im normierten Plugin-Betrieb erst nach erfolgreichem Abschluss beider
Kalibrierungen Teleoperation starten.

1. Arm in die SO-101-Mittel-/Referenzpose bringen und ENTER drücken. Die sechs
   Rohpositionen werden als hostseitige Nullpunkte `homing_offset` gespeichert.
   Die Pose ist am realen Arm abzugleichen; es werden keine Servo-Offsets geschrieben.
2. Nacheinander jedes Gelenk langsam durch seinen benutzbaren Bereich bewegen.
   ENTER startet bzw. beendet die Aufnahme pro Gelenk. Alle sechs Achsen werden
   während der Aufnahme überwacht, kein Gelenk wird automatisch gefahren.
   Die Anzeige `raw`, `min`, `max` zeigt die gemessenen Werte des aktuellen Gelenks.
   Ändert sich dessen Wert nicht, bricht die Routine direkt nach diesem Gelenk ab.
   Bei blockiertem Gelenk keine Kraft anwenden; Portzuordnung und Torque-Freigabe klären.
3. Ein Sprung um mehr als 2048 Ticks zwischen Abtastungen wird als möglicher
   Encoderübergang `4095↔0` behandelt: Abbruch mit Fehlermeldung statt Wrap-Korrektur.
   Auch zu schnelle Bewegungen können diesen konservativen Abbruch auslösen.
   Die Fehlermeldung nennt Gelenk, vorherigen/aktuellen Rohwert, Differenz und
   beide vollständigen Messvektoren. Alle Gelenke werden überwacht; ein
   Greifer-Ausreißer kann deshalb auch während der Basisaufnahme abbrechen.
   Die Meldung allein beweist keinen echten Encoderübergang.
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

Für den ersten Test ohne Kameras gibt es eine eigene Konfiguration. Mit den
aktuell vom Nutzer zugeordneten Ports Follower COM13 / Leader COM14:

```powershell
uv run lerobot-teleoperate --config_path=examples/nexarm/teleoperate_no_cameras.yaml --robot.port=COM13 --teleop.port=COM14
```

Ein CLI-Override mit `--robot.cameras="{}"` leert die bereits aus der YAML
gelesenen Kameraeinträge am gepinnten Parser nicht zuverlässig. Dafür die
separate Konfiguration verwenden; COM-Zuordnung bei anderer Hardware neu prüfen.

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
- **Follower antwortet beim Kalibrieren nicht:** Bei bestätigtem Follower-Port
  und eingeschalteter externer Versorgung kann ein Mensch den Transport ausgeben:
  `uv run --locked python scripts/diagnose_nexarm.py --port=COM13`.
  Arm vorher abstützen. Der Aufruf verwendet denselben Bridge-/Torque-off-Pfad,
  sendet keine Positionsziele und benötigt keine Kalibrierung. Er zeigt TX sowie
  empfangene RX-Bytes und sendet beim Beenden den Bridge-Ausgangsbefehl. Ein Timeout ohne RX
  und empfangene, aber nicht parsebare Frames sind unterschiedliche Befunde.
  Für einen ausdrücklichen Vergleichstest bei vermutetem Neustart durch die
  Portöffnung: `uv run --locked python scripts/diagnose_nexarm.py --port=COM13 --startup-wait=2`.
  Nur dieser Diagnoseaufruf wartet zusätzlich vor dem ersten Bridge-Befehl;
  das normale Treiberverhalten wird dadurch nicht geändert, RTS/DTR werden
  nicht umgeschaltet. Das ist eine unbestätigte Diagnosehypothese, kein Firmware-Fix.
  Mit zusätzlichem `--probe-before-torque-off` wird ausdrücklich einmal vor dem
  Torque-off-Befehl gelesen, um den Einfluss dieses Befehls zu untersuchen.
  Der anfängliche Hardware-Torque-Zustand ist dabei unbekannt; der Test sendet
  weiterhin weder Torque-on noch Positionsziele. Diese Option ist kein
  Kalibrierungsmodus und verändert den Produktionstreiber nicht.
  `--inactive-control-lines` ist ein weiterer ausdrücklicher Diagnosevergleich:
  DTR und RTS werden vor dem Öffnen auf False gesetzt, um einen möglichen
  RTS-/DTR-bedingten Reset zu untersuchen. Beispiel:
  `uv run --locked python scripts/diagnose_nexarm.py --port=COM13 --startup-wait=2 --inactive-control-lines`.
  Default bleibt die ursprüngliche Portöffnung. Die Wirksamkeit dieser Option
  auf der konkreten NexArm-Platine ist noch nicht nachgewiesen; sie ist kein
  Firmware-Update und keine Änderung des installierten Robotertreibers.
  Bleibt der Follower stumm, kann die USB-Verbindung unabhängig von der Servo-Bridge
  geprüft werden. Follower abstützen, ausschalten und USB abziehen; dann wieder
  einschalten, USB anschließen und den Start abwarten. Im normalen Firmwaremodus:
  `uv run --locked python scripts/diagnose_nexarm.py --port=COM13 --controller-probe --startup-wait=5 --inactive-control-lines`.
  Dieser Modus sendet ausschließlich die Herstellerabfrage CMD 1 für die
  Firmwareversion, keine Bridge-, Torque- oder Positionsbefehle. Eine Version
  bestätigt die Controllerkommunikation; ein Timeout identifiziert die installierte
  Firmware nicht. In einer bereits aktiven Bridge ist diese Abfrage nicht verlässlich.
  Der Aufruf ist ein Hardwaretest und wird nicht vom Agenten ausgeführt.
- **0-/4095-Ausreißer trotz erfolgreicher Antwort:** Ein menschlicher Test hat
  ein CMD-96-Paket mit gültiger Prüfsumme, aber Werten wie -1 und 21197 gezeigt.
  Der alte Treiber begrenzt solche Werte und kann dadurch ungültige Messungen
  verdecken. Plugin, Rohwertskript und Diagnose verwenden deshalb
  `ValidatedNexArmMotorsBus`: Positionsantworten müssen CMD 96, genau zwölf Bytes
  und sechs Werte in 0..4095 enthalten. Ungültige Antworten erscheinen mit
  Warnung und werden innerhalb der vorhandenen drei Versuche erneut angefragt.
  Bleiben alle Versuche erfolglos, bricht das Lesen ab. Die Diagnose zeigt die
  Zahl verworfener Positionsantworten. Es werden keine letzten Werte als Ersatz
  verwendet. Echte Werte 0/4095 bleiben erlaubt; Wrap-Erkennung und die separate
  Greifer-Kalibriergrenze bleiben bestehen. Die originale `bus.py` bleibt unverändert.
- **Port busy:** Hiwonder-Tool, Arduino-Monitor und andere LeRobot-Prozesse schließen.
- **Kamerabilder veraltet:** Der Windows-Fallback wartet per `async_read` auf ein
  neues Bild. Andere Kameraprogramme schließen und Indizes/`fourcc` prüfen.
- **Rerun-Speicherlimit / Transportfehler:** Der Viewer hält eine begrenzte
  Historie; das Verwerfen alter Daten am Speicherlimit ist vorgesehen. Das
  Rohwertskript überträgt Livebilder komprimiert und zeitabhängig. Ein gRPC-
  Transportfehler bedeutet einen Abbruch der Viewer-Verbindung; die genaue
  Ursache ergibt sich daraus nicht. Alten Lauf mit Strg+C beenden, altes
  Rerun-Fenster schließen und neu starten. Mit `--no-display-data` lässt sich
  die Teleoperationsrate bei weiterhin aktiven Kameras ohne Viewer vergleichen.
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

## Cloud-Inferenz (FLUX 3 Action auf vast.ai)

`uv run cloud/deploy.py up` mietet die günstigste RTX 5090, installiert LeRobot mit
FLUX 3 Action nach der BFL-Anleitung, lädt das SO-101-Modell und öffnet die API unter
`http://127.0.0.1:8000`. `uv run cloud/deploy.py down` stoppt die Instanz wieder.
Voraussetzungen, Ablauf und API stehen in [cloud/README.md](cloud/README.md).