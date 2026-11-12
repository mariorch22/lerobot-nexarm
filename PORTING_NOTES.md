# NexArm-Portierung: Befund, Plan und offene Fragen

Stand: 12.11.2026, nach Freigabe der Antworten Q1–Q8: Plugin, Kalibrierung,
Beispiele und Tests sind umgesetzt. Der Quellenvergleich aus dem ersten
Dokumentationsschritt bleibt erhalten. Installation und Tests erfolgen ausschließlich
in `lerobot-nexarm`; es werden keine echten Serial-Ports oder Kameras geöffnet.
Die frühere Beschränkung auf diese eine Datei wurde durch den Umsetzungsauftrag aufgehoben.

## 1. Auftrag und kurzer Plan

Ziel des späteren Pakets sind `nexarm_follower`, `nexarm_leader` und ein eigener
CommProtocol-Treiber neben unverändertem Upstream-LeRobot. F3A-Training, Policy-Server,
Perception und RL bleiben außerhalb dieses Meilensteins.

1. **Quellen sichern und vergleichen:** Herstellerfassung als Grundlage verwenden;
   Unterschiede zur früher verwendeten Kopie und Hardwarekonflikte dokumentieren.
   Ergebnis dieses Schritts: Abschnitte 2–6 dieser Datei.
2. **Blockierende Fragen klären:** insbesondere Vorzeichen im Gradmodus,
   Kalibrierungskoordinaten beim Leader-Mapping und Drehmomentverhalten.
   Die betroffenen Teile bis zur Klärung nicht implementieren.
3. **Paket und Discovery vorbereiten:** Python 3.12, `uv`, eigener Namespace,
   importierbares Plugin mit beiden Config-Registrierungen; keine Upstream-Patches.
   LeRobot als Git-Abhängigkeit exakt auf
   `2f05d8f64d62a865c368a9fdf0ba3d8423e28035` pinnen; optionales Extra `cloud`
   mit `lerobot[flux3]` an genau demselben Commit.
4. **Treiber und Geräte portieren:** Protokollverhalten erhalten; anschließend
   validierte Kalibrierung und Rohwert-Konvertierung in Robot/Teleoperator ergänzen.
   Features, Kameras und Standard-Prozessoren mit dem gepinnten API verbinden.
5. **Ohne Hardware prüfen:** feste Frame-Testvektoren, Mapping, Konvertierung,
   Kalibrierungsdateien, gemockte Serial-Lebenszyklen und Discovery nach Installation.
   Abschließender Pakettest ist `uv run pytest`.
6. **Beispiele und README vervollständigen:** aktuelle CLI-Schemata, Windows-Ports,
   Kameras, Kalibrierung/Vorzeichen, Troubleshooting und kontrolliertes Bump-Verfahren.
   Danach übernehmen Menschen die Hardwareabnahme in der vorgegebenen Reihenfolge.

## 2. Quellenstand und Vergleichsmethode

Alle folgenden Pfade sind relativ zu `C:\Users\mario\robot`:

- **U:** `lerobot/`, HEAD = `2f05d8f64d62a865c368a9fdf0ba3d8423e28035`.
  Der verlangte Pin ist vorhanden, einschließlich `src/lerobot/policies/flux3/`.
  Ein gezielter Git-Diff gegen HEAD zeigte keine Änderungen an den untersuchten
  SO-Follower-/SO-Leader-Dateien, Motor-Dateien, Basisklassen, `import_utils.py`,
  `integrate_hardware.mdx` und `pyproject.toml`.
- **H:** `hiwonder-fork/`, HEAD = `e99c55af4bd0c1fffa732cb3b39cef9a4323ba79`.
  Maßgeblich ist die vorhandene Arbeitskopie: NexArm-Dateien sind dort ungetrackt,
  Integration und weitere Dateien weisen bereits Änderungen auf. Der HEAD allein
  beschreibt daher die NexArm-Quelle nicht vollständig. Nichts daran verändert.
- **O:** `old/finsh/`, die frühere Herstellerkopie. `git rev-parse HEAD` liefert dort
  keinen gültigen Commit; der Vergleich bezieht sich auf die vorhandenen Dateien.
- `old/lerobot/` ist laut `old/README.md` nur eine separate Upstream-Referenz,
  nicht die früher installierte Herstellerfassung. Die Suche in dessen `src/` und
  `examples/` fand keine NexArm-Integration.
- Ziel ist das bereits vorhandene Repo `lerobot-nexarm/`; kein zweites Repo anlegen.
  Zu Beginn enthält es nur die unveränderte `README.md` mit dem Projektnamen.

Die drei NexArm-Verzeichnisse und `examples/nexarm/` wurden rekursiv über die
Vereinigung beider Dateilisten verglichen. SHA-256 verifiziert Bytegleichheit;
abweichende Textdateien wurden zusätzlich per `git diff --no-index` geprüft.
NexArm-README, Tests und die unten genannten Integrationsdateien wurden ebenfalls
verglichen. Generierte Bytecode-Dateien sind separat aufgeführt.
`old/archive/` und alte Umgebungen wurden nicht als Implementierungsquelle verwendet.

## 3. Vollständiger Vergleich H gegen O im NexArm-Umfang

### 3.1 Identische Quellen

Für folgende Dateien besteht Bytegleichheit zwischen H und O:

| Relativer Pfad in beiden Herstellerkopien | Befund |
| --- | --- |
| `src/lerobot/motors/nexarm/__init__.py` | Identisch |
| `src/lerobot/motors/nexarm/nexarm.py` | Identisch; auch Frames, Checksummen, Mapping und Timing |
| `src/lerobot/robots/nexarm_follower/__init__.py` | Identisch |
| `src/lerobot/robots/nexarm_follower/config_nexarm_follower.py` | Identisch |
| `src/lerobot/robots/nexarm_follower/nexarm_follower.py` | Identisch |
| `src/lerobot/robots/nexarm_follower/nexarm.md` | Identisch |
| `src/lerobot/teleoperators/nexarm_leader/__init__.py` | Identisch |
| `src/lerobot/teleoperators/nexarm_leader/config_nexarm_leader.py` | Identisch |
| `src/lerobot/teleoperators/nexarm_leader/nexarm_leader.py` | Identisch |
| `examples/nexarm/inference.yaml` | Identisch |
| `examples/nexarm/train.yaml` | Identisch; Training bleibt außerhalb des Auftrags |
| `README_NEXARM.md` | Identisch |
| `tests/motors/test_nexarm.py` | Identisch |
| `tests/robots/test_nexarm_follower.py` | Identisch |
| `pyproject.toml` | Identisch; enthält Hersteller-Extra `nexarm` |
| `src/lerobot/robots/utils.py` | Identisch; expliziter NexArm-Factory-Zweig |
| `src/lerobot/teleoperators/utils.py` | Identisch; expliziter NexArm-Factory-Zweig |
| `src/lerobot/scripts/lerobot_{calibrate,find_joint_limits,record,replay,rollout,teleoperate}.py` | Alle sechs Dateien jeweils identisch; enthalten direkte NexArm-Imports |

Es gibt in den verglichenen Quell-/Beispielverzeichnissen keine nur einseitig
vorhandenen Dateien. Insbesondere wurde keine abweichende Protokollimplementierung
in O gefunden. Die Bezeichnung „bekannt gelaufen“ ist kein neuer Hardwaretest und
bestätigt nicht automatisch jede Konfiguration oder jeden alten Test.

### 3.2 Sämtliche Unterschiede in `examples/nexarm/`

| Datei / Feld | H | O | Einordnung |
| --- | --- | --- | --- |
| `teleoperate.yaml`: Kopfkommentare | Titel, Aufrufbeispiel vorhanden | Entfernt | Dokumentation |
| `teleoperate.yaml`: `robot.port` | `COM19` plus Plattformkommentare | `COM9`, ohne Kommentare | Gerätezuteilung offen, siehe Q8 |
| `teleoperate.yaml`: `teleop.port` | `COM18` plus Plattformkommentare | `COM10`, ohne Kommentare | Gerätezuteilung offen, siehe Q8 |
| `teleoperate.yaml`: beide Kameras `fourcc` | Nicht gesetzt | Jeweils `"MJPG"` | Geändertes Aufnahmeformat, siehe Q8 |
| `teleoperate.yaml`: `display_data` | `false` | `true` | Lokale Visualisierung |
| `teleoperate.yaml`: Dateiende | Abschließender Zeilenumbruch | Kein abschließender Zeilenumbruch | Rein textuell |
| `record.yaml`: Kopfkommentare | Titel, Aufrufbeispiel vorhanden | Entfernt | Dokumentation |
| `record.yaml`: `robot.port` | `COM19` plus Plattformkommentare | `COM9`, ohne Kommentare | Gerätezuteilung offen, siehe Q8 |
| `record.yaml`: `teleop.port` | `COM18` plus Plattformkommentare | `COM10`, ohne Kommentare | Gerätezuteilung offen, siehe Q8 |
| `record.yaml`: beide Kameras `fourcc` | Nicht gesetzt | Jeweils `"MJPG"` | Geändertes Aufnahmeformat, siehe Q8 |
| `record.yaml`: `dataset.repo_id` | `local/nexarm_pick` | `local/nexarm_test` | Lokales Aufnahmeziel |
| `record.yaml`: `dataset.single_task` | `pick up the object` | `Put the cube into the bowl` | Aufgabentext |
| `record.yaml`: `dataset.num_episodes` | `50` | `3` | Aufnahmeparameter |
| `record.yaml`: `dataset.episode_time_s` | `10` | `20` | Aufnahmeparameter |
| `record.yaml`: `dataset.reset_time_s` | `10` | `15` | Aufnahmeparameter |
| `record.yaml`: Leerraum | Eine Leerzeile vor `teleop` | Zwei Leerzeilen | Rein textuell |
| `record.yaml`: Dateiende | Abschließender Zeilenumbruch | Kein abschließender Zeilenumbruch | Rein textuell |

Unverändert sind jeweils 1 Mbps, `front` auf Index 1, `wrist` auf Index 2,
640×480 und 30 fps. Bei Recording bleiben `video: true`, `push_to_hub: false`,
`display_data: false` und `play_sounds: true` gleich; Teleoperation bleibt bei 30 fps.
Die spätere Übernahme von MJPG wurde in Q8 ausdrücklich freigegeben;
Ports und Indizes bleiben kommentierte Platzhalter.

### 3.3 Generierte Dateien

Die folgenden acht Dateien existieren auf beiden Seiten und unterscheiden sich binär:

- `src/lerobot/motors/nexarm/__pycache__/__init__.cpython-312.pyc`
- `src/lerobot/motors/nexarm/__pycache__/nexarm.cpython-312.pyc`
- `src/lerobot/robots/nexarm_follower/__pycache__/__init__.cpython-312.pyc`
- `src/lerobot/robots/nexarm_follower/__pycache__/config_nexarm_follower.cpython-312.pyc`
- `src/lerobot/robots/nexarm_follower/__pycache__/nexarm_follower.cpython-312.pyc`
- `src/lerobot/teleoperators/nexarm_leader/__pycache__/__init__.cpython-312.pyc`
- `src/lerobot/teleoperators/nexarm_leader/__pycache__/config_nexarm_leader.cpython-312.pyc`
- `src/lerobot/teleoperators/nexarm_leader/__pycache__/nexarm_leader.cpython-312.pyc`

Bytecode ist keine zusätzliche Quellcodefassung und wird weder kopiert noch ausgeführt.
Die binären Abweichungen wurden nicht als Beleg für andere Hardwarelogik interpretiert.

### 3.4 Zusätzliche NexArm-Hinweise aus `old/`

- `old/teleoperate_no_cameras.yaml`: Follower `COM4`, Leader `COM3`, beide 1 Mbps,
  `cameras: {}`, `display_data: false`, 30 fps. Das ist ein dritter Port-Satz neben
  H und O, keine bestätigte aktuelle Zuteilung.
- `old/README.md` und `old/pyproject.toml`: früheres Python-3.12-/uv-Projekt mit
  editierbarem `finsh`, Extra `lerobot[nexarm]`, CPU-Torch `2.10.0` und
  Torchvision `0.25.0`. Diese alten Torch-Pins werden nicht zum neuen Paketvertrag.
  Beide LeRobot-Fassungen teilen den Importnamen `lerobot`; der Fork darf nicht
  zusätzlich zum gepinnten Upstream in derselben neuen Umgebung installiert werden.
- `old/README.md` sagt ausdrücklich, dass bei der damaligen Einrichtung
  Teleoperation, Replay und Rollout nicht gestartet wurden. Daraus folgt kein
  belegter erfolgreicher Bewegungsversuch mit einem bestimmten YAML.
- `old/outputs/` enthält Kamerabilder `opencv_0.png`, `opencv_1.png`, `opencv_2.png`
  in `captured_images`, `camera_check`, `camera_check_dshow`,
  `camera_check_release` und `camera_check_sequential`; unter
  `camera_check_sequential_repeat` liegt nur `opencv_0.png`.
  Das belegt vorhandene Aufnahme-Artefakte, keine aktuelle Zuordnung zu `front`
  oder `wrist` und keinen bestimmten zuverlässigen Backend-/FPS-Betrieb.
- `old/test_image_loading.py` prüft Bilddateiladen und Dateifreigabe; es liefert
  keine NexArm-Protokollparameter. Kein experimenteller Code wird übernommen.

## 4. API-Unterschiede und geplante Behandlung

| Thema | Herstellerfassung H | Gepinnter Upstream U / geplanter Umgang |
| --- | --- | --- |
| Basisklassen | `Robot` / `Teleoperator`, gleiche wesentliche abstrakte Gerätemethoden | Weiter direkt davon ableiten. Externe absolute Imports statt relativer Imports innerhalb des Upstream-Paketbaums. `config_class` und `name` bleiben gesetzt. |
| Typen | Basisklassen importieren `lerobot.types` | Aktuell `lerobot.lerobot_types` für `RobotAction` / `RobotObservation`. Dict-basierte Schnittstelle bleibt. |
| Config-Registrierung | Dataclasses mit `RobotConfig.register_subclass` bzw. `TeleoperatorConfig.register_subclass` | Mechanismus und Basiskonfiguration (`id`, `calibration_dir`) sind gleich. Namen `nexarm_follower` / `nexarm_leader` beibehalten, Registrierung durch Plugin-Import auslösen. |
| Factory / Discovery | NexArm-Verzweigungen in Factories und Imports in CLI-Dateien | Unveränderte Upstream-Factories nutzen `make_device_from_device_class`. Installiertes Plugin muss vor dem Parsen registriert werden; Details unten. |
| Motorbus | Eigenständiger `NexArmMotorsBus`, keine Ableitung vom generischen Motorbus | Eigenständig lassen. SO verwendet inzwischen `SerialMotorsBus` / rustypot für STS3215; das ist kein Treiber für die NexArm-Bridge. Keine STS3215-Register-, PID-, Mode- oder Motor-Setup-Kommandos übernehmen. |
| Kalibrierungsformat | `MotorCalibration`: `id`, `drive_mode`, `homing_offset`, `range_min`, `range_max` | Dieselben fünf Felder bestehen weiter. JSON pro Gerät/ID und Standardpfade übernehmen; validierte Bereiche und Richtung statt alter Platzhalter. Q1, Q2 und Q4 klären. |
| Kalibrierungsablauf | `calibrate()` schreibt für alle Achsen pauschal `0..4095`, Offset `2048`, `drive_mode=0`; Werte werden für I/O nicht benutzt | SO zeichnet Bereiche auf, setzt Homing und schreibt Motorkalibrierung. NexArm braucht manuelles Bewegen mit torque off und CMD 96, Speicherung im Host und Software-Konvertierung; die Bridge bietet keine dokumentierten Registerbefehle für Homing. |
| Datei wiederverwenden | Alte Basisklassen laden JSON; NexArm akzeptiert schon irgendeinen nichtleeren Inhalt oder Dateiexistenz | Upstream hat zusätzlich `_keep_calibration_file(bus)`, das `disable_torque()` und `write_calibration()` aufruft. Nicht blind auf NexArm anwenden. Eigenen Wiederverwendungsdialog mit Inhaltsprüfung planen; keine erfundenen Firmware-Schreiboperationen. |
| Kalibrierungsverzeichnis | Robot legt Verzeichnis im Konstruktor an | U-Robot erst beim Speichern; Teleoperator weiterhin im Konstruktor. Standardpfad und Schreibverhalten berücksichtigen, Tests auf temporäre Verzeichnisse begrenzen. |
| Einheiten | NexArm gibt Rohpositionen als `float` aus und akzeptiert rohe Zielwerte | SO verwendet Grad bzw. Prozent-/Bereichswerte. Konvertierung muss vor Rückgabe an LeRobot und vor Serial-Schreiben innerhalb der Geräte erfolgen, nicht erst in der Policy. Siehe Abschnitt 5. |
| Motor-Features | Sechs `<joint>.pos: float` in fester Reihenfolge | Gleiche Keys, IDs und Reihenfolge; ab jetzt Werte in SO-Einheiten. Features müssen ohne Verbindung verfügbar sein. |
| Kameras | Konfigurierbare Namen; RGB-Shape `(height, width, 3)`; `read_latest()`, bei Timeout `async_read(timeout_ms=2000)` | Beide Lese-APIs existieren am Pin. Bestehenden Windows-Fallback erhalten. SO kann zusätzlich optionale Depth-Features; für unsere zwei OpenCV-RGB-Kameras ist keine Depth-Erweiterung nötig. |
| Feedback des Leaders | `feedback_features={}`, `send_feedback()` ohne Wirkung | SOLeader kann Positionen zurückgeschrieben bekommen. Für NexArm keine neue aktive Leader-Ansteuerung ergänzen; leere Feedback-Fähigkeiten beibehalten. |
| Prozessoren | Teleoperate/Record verwenden bereits `make_default_processors()` | U verwendet weiterhin drei Identity-Pipelines für Teleop-Aktion, Robot-Aktion und Beobachtung. Kein zusätzliches NexArm-Normalisierungs-Plugin und keine doppelte Konvertierung. Policy-Prozessoren bleiben für ihre eigenen Statistiken zuständig. |
| `send_action()` | CMD 97, danach CMD 96; Rückgabe gemessener Positionen, bei Timeout gesendete Ziele | SO gibt angewendete Zielwerte zurück. U-Recording speichert die Rückgabe als Aktion. Rückgabe, Readback und deren Timing nicht stillschweigend ändern; Q6. |
| Lifecycle | Idempotente NexArm-Verbindungen; Leader torque off; Follower Bridge an/aus, torque on beim Konfigurieren | SO verwendet Verbindungs-Dekoratoren. Schnittstellen kompatibel machen, aber bestehende NexArm-Befehlsfolgen und Torque-Defaults nicht allein zum Angleich an SO verändern; Q3/Q5. Fehlerbereinigung der Bridge ausdrücklich mit Mocks prüfen. |
| Halteverhalten | Kein explizites Hold-Opt-in | U-Robot bietet `supports_command_hold`, `supports_position_hold`, `hold()`; SO aktiviert Position-Hold. NexArm nicht automatisch für zusätzliche Hold-/Homing-Bewegungen freischalten; Q7. |
| CLI / Beispiele | Direkte Hersteller-Imports, YAMLs und `python -m ...` | Standard-Entry-Points mit `uv run lerobot-*`; `--config_path` gegen aktuelle Dataclasses prüfen. `lerobot-calibrate` verbindet mit `calibrate=False`, ruft dann `calibrate()` auf und trennt im `finally`. |

### 4.1 Plugin-Konvention am Pin

Maßgeblich: U `src/lerobot/utils/import_utils.py:184` und `:249` sowie
`docs/source/integrate_hardware.mdx`, Abschnitt „Plugin“.

- Der Scanner liest **installierte Distributionen** über `importlib.metadata`.
  Deren `Name` muss mit `lerobot_robot_`, `lerobot_teleoperator_` oder einem anderen
  dort unterstützten Präfix beginnen. Er importiert genau diesen Namen.
  Ein alleiniger Distributionsname `lerobot-nexarm` wird nicht erkannt;
  nur ein passend benanntes Python-Modul daneben reicht ebenfalls nicht.
  Dieser Mechanismus verwendet keine Plugin-Entry-Point-Gruppe.
- Geplanter Aufbau: Repo weiter `lerobot-nexarm`, eine Distribution mit dem
  erkannten Namen `lerobot_robot_nexarm`, deren gleichnamiger Import beide
  Configs registriert. Robot und Teleoperator können in diesem einen Paket liegen;
  der Scanner erzwingt keine getrennten Distributionen für die beiden Gerätetypen.
  Gemeinsamer Serial-Treiber bleibt paketintern, ohne Erweiterung von `lerobot/`.
- `NexArmFollowerConfig` muss zu `NexArmFollower` und `NexArmLeaderConfig` zu
  `NexArmLeader` führen. Factory-Suchorte sind Config-Modul, Elternpaket,
  Elternpaket plus kleingeschriebener Klassenname und das Modul ohne `config_`.
  Geräte und Configs aus dem Paket-`__init__.py` exportieren.
- Im späteren Installationstest den tatsächlich erzeugten Metadata-`Name`
  einschließlich Bindestrich-/Unterstrichbehandlung prüfen. Danach in einem
  frischen Prozess nur `register_third_party_plugins()` aufrufen und beide
  Configs sowie Geräte über die LeRobot-Factories erzeugen, ohne `connect()`.
  Ein Test mit vorherigem manuellem NexArm-Import würde die Discovery nicht belegen.
- Calibrate, Teleoperate und Record rufen den Scanner vor dem Parsen auf.
  `lerobot-find-port` ist dagegen ein generisches Enumerationstool ohne
  `--robot.type` / `--teleop.type`; dafür gibt es nichts NexArm-spezifisch zu registrieren.

### 4.2 Beispiele, Abhängigkeiten und Dokumentation

Später `teleoperate.yaml`, `record.yaml` und `inference.yaml` auf Basis der
Herstellerdateien neu prüfen: `COM19`/`COM18` nur als Windows-Platzhalter,
explizite Geräte-IDs für getrennte Kalibrierungen, Kameras `front` und `wrist`,
640×480 bei 30 fps. Konfigurationsfelder für Kameraindizes, Namen und Format
bleiben änderbar. `fourcc: MJPG` ist nach Entscheidung Q8 Windows-Beispieldefault.

`inference.yaml` nutzt `lerobot-rollout`, `strategy.type=sentry` und einen separat
anzugebenen `policy.path`. Diese Schnittstelle gibt es am Pin weiterhin; Laufzeit-,
Dataset- und Policy-Konfiguration müssen trotzdem gegen `rollout/configs.py`
validiert werden. Daraus folgt keine Implementierung eines Policy-Servers oder
F3A-Trainings. Automatische Rückkehr zur Startpose ist gesondert zu beachten (Q7).

Das alte Extra `lerobot[nexarm]` existiert im Upstream nicht. Direkte pyserial-
Abhängigkeit vorsehen und für die dokumentierten CLIs die benötigten Upstream-
Extras berücksichtigen (`core_scripts` bündelt Dataset, Hardware und Visualisierung).
Auch das `cloud`-Extra muss dieselbe vollständige Git-Revision verwenden.
Installation und CLI-Importe sind später tatsächlich zu prüfen, nicht hier als
bereits funktionierend vorauszusetzen.

README muss `uv`/venv auf Windows, Pin-Installation plus editierbares Plugin,
Port-/Kamerasuche, Kalibrierung mit manuellen Richtungen, Teleoperation und
Recording erklären. Troubleshooting: Bridge-Modus, beide Checksummen, belegte
COM-Ports; unter WSL USB per usbipd anbinden und unzuverlässige USB-Kameras erwähnen.
Ein Pin-Bump ist ein separater bewusster Schritt: API-/Discovery-/Einheiten-Diff,
Tests und Beispiele erneut prüfen, beide Git-Pins gemeinsam ändern und erst
danach menschliche Hardwareabnahme. Kein automatisches Upgrade.

## 5. Erhaltenes Hardwareverhalten und genaue Normalisierung

### 5.1 Protokoll und Mapping

Quelle: H/O `src/lerobot/motors/nexarm/nexarm.py:42–114` und `:124–255`.

- HX-30HM, Positionen `0..4095`, 1 Mbps. System-ID `0xFF`; Frame
  `FF FF ID LEN CMD ARGS... CHECKSUM`, `LEN=len(ARGS)+2`.
  Gesendete Prüfsumme: `(~sum(ID, LEN, CMD, ARGS...)) & 0xFF`.
- Empfang akzeptiert unverändert die vollständige Prüfsumme **und**
  `(~sum(ID, LEN, CMD)) & 0xFF`, also die kurze fehlerhafte Leader-Prüfsumme.
  Der bestehende Parser toleriert beide generell, nicht nur nach einer Rollenprüfung.
- CMD 96 fordert sechs Positionen an; Antwortdaten sind sechs Little-Endian-`int16`
  (12 Byte). Bestehender Treiber begrenzt gelesene Werte auf `0..4095` und versucht
  standardmäßig insgesamt dreimal; Firmware-Debugtext kann den Datenstrom stören.
- CMD 97 schreibt sechs Little-Endian-`int16` ohne Antwort. CMD 98 nutzt Argument
  `1`/`0` für Torque an/aus; CMD 68 ebenso für Bridge an/aus, ausschließlich Follower.
- Timing erhalten: Serial-Timeout/Write-Timeout 50 ms, Reply-Timeout 150 ms,
  nach Portöffnung 100 ms, Torque 20 ms, Bridgewechsel 100 ms, zwischen Read-Retries
  5 ms; Buffer-Resynchronisierung und Serial-Lock nicht beiläufig entfernen.
- Leader-Mapping rundet/begrenzt zunächst raw; für `shoulder_lift` anschließend
  `4096-pos`, zum Schluss erneut Begrenzung auf `0..4095`.
  Daher wird raw `0` zu `4095`, nicht zu `4096` oder `4095-pos`.
- Zusätzliche alte Greiferabbildung: `2833 + (pos-2048)*4`, begrenzt auf
  `[1195,2833]`. Das ist mehr als ein Bereichslimit und muss bei Q2 berücksichtigt werden.
  Der alte Bus und Follower begrenzen allgemeine Writes nur auf `0..4095`;
  die spezielle Greiferbegrenzung liegt bisher im Leader-Mapping. Für die neue
  normalisierte Follower-Schnittstelle gilt der vorgegebene Greiferbereich auch
  für Policy-Aktionen; die Einbindung in Kalibrierung und Mapping bleibt Q2/Q4.
- Der bisherige Positionsleser prüft Nutzdatenlänge, aber nicht explizit, ob die
  Antwort-CMD zu CMD 96 passt. Keine Änderung der Antwortakzeptanz als beiläufiges
  „Aufräumen“; etwaige spätere Protokollhärtung separat begründen.

### 5.2 SO-Konvention am exakten Upstream-Pin

Quellen: U `robots/so_follower/config_so_follower.py:41–42`,
`robots/so_follower/so_follower.py:67–79`,
`teleoperators/so_leader/config_so_leader.py:29–30` und
`motors/motors_bus.py:1010–1067` (jeweils unter `src/lerobot/`).

| Kanäle | Default `use_degrees=True` | Option `use_degrees=False` |
| --- | --- | --- |
| IDs 1–5, fünf Armachsen | `MotorNormMode.DEGREES` | `MotorNormMode.RANGE_M100_100`, `[-100,100]` |
| ID 6, Greifer | Immer `MotorNormMode.RANGE_0_100`, `[0,100]` | Ebenfalls `[0,100]` |

Das sind die von LeRobot sichtbaren Hardwareeinheiten. Insbesondere ist
`[-100,100]` am Pin **nicht** der Default der fünf Armachsen.

Mit Kalibrierungsgrenzen `a=range_min`, `b=range_max`, `m=(a+b)/2`, `b>a` und
`c=clip(raw,a,b)` berechnet der gepinnte Motorbus:

| Modus | raw → LeRobot | LeRobot → raw |
| --- | --- | --- |
| `RANGE_M100_100` | `v=200*(c-a)/(b-a)-100`; bei invertiertem `drive_mode`: `-v` | Vorzeichen rückgängig machen, auf `[-100,100]` begrenzen; `int((v+100)/200*(b-a)+a)` |
| `RANGE_0_100` | `v=100*(c-a)/(b-a)`; bei invertiertem `drive_mode`: `100-v` | Inversion rückgängig machen, auf `[0,100]` begrenzen; `int(v/100*(b-a)+a)` |
| `DEGREES` | `(raw-m)*360/4095` bei 12 Bit | `int(v*4095/360+m)` |

Gradwerte haben damit keinen festen, kalibrierungsunabhängigen Bereich `[-100,100]`
oder `[-180,180]`; Endpunkte hängen vom erfassten Bewegungsbereich ab.
Der Grad-Zweig verwendet den ungeclippten Rohwert und wendet `drive_mode` im
untersuchten Code nicht an. Die Umkehrfunktion ebenfalls nicht. `int()` kürzt
ab, während die alte NexArm-Aktionsschnittstelle `round()` verwendet. Diese Details
sind relevant und dürfen beim Nachbauen nicht unbemerkt abweichen (Q1).

Die Richtung kann ohne neues JSON-Feld als `drive_mode=0` für Signum `+1` und
`drive_mode=1` für Signum `-1` dokumentiert werden. Das ist ein geplanter
Softwarevertrag des Plugins, kein Schreiben eines HX-30HM-Drive-Mode-Registers.
Für den Gradmodus muss der Konflikt mit U ausdrücklich gelöst werden.
Bereichsinversion des Greifers erfolgt um 50 (`100-v`), nicht als negatives Prozent.

### 5.3 Kalibrierung und Policy-Vertrag

Standard-Dateien entsprechend den Basisklassen:

- `${HF_LEROBOT_CALIBRATION}/robots/nexarm_follower/<id>.json`
- `${HF_LEROBOT_CALIBRATION}/teleoperators/nexarm_leader/<id>.json`

Ohne Umgebungs-Override ist `HF_LEROBOT_CALIBRATION` unter
`HF_LEROBOT_HOME/calibration`, standardmäßig unter `HF_HOME/lerobot/calibration`.
`calibration_dir` kann den gerätespezifischen Ordner überschreiben.
Quelle: U `utils/constants.py:63–101`, `robots/robot.py:59–68,163–184` und
`teleoperators/teleoperator.py:48–59,144–172`.

Geplant ist JSON mit einem Eintrag pro unverändertem Jointnamen und den fünf
`MotorCalibration`-Feldern. Min/Max werden manuell durch Bewegen erfasst,
Richtung zunächst explizit dokumentiert und später von Menschen pro Joint gesetzt.
Vollständigkeit aller sechs IDs, gültige Grenzen und zulässige Richtungen prüfen;
Dateiexistenz allein reicht nicht. Ohne gültige Kalibrierung keine Aktionen senden.
`connect(calibrate=False)` muss dennoch den Kalibrierungs-CLI ermöglichen; dazu
müssen Rohlesen und normierte Aktionsfreigabe getrennt sein (Q5).

SO kalibriert `wrist_roll` als volle Umdrehung und schreibt Homing/Limit-Register.
Das ist für NexArm nicht belegt. Alle NexArm-Gelenke wie beauftragt tatsächlich
vermessen, keine volle freie Wrist-Umdrehung und keine Firmware-Offsetschreibfunktion
erfinden. Software-Zentrierung, eventueller Encoder-Wrap und Altdateien siehe Q4.

F3A-Prozessoren normalisieren anschließend für das Modell; das ersetzt nicht die
Rohencoder-Konvertierung im Gerät. U `docs/source/flux3.mdx`, „Defaults and
normalization“, weist darauf hin, dass gespeicherte Quantile Gelenkreihenfolge,
Einheiten und Kalibrierung voraussetzen und keine universellen SO-101-Werte sind.
„raw states/actions“ dort bedeutet Eingabedaten vor der Modellnormalisierung;
es ist keine Aufforderung, die NexArm-Encoderwerte unverändert als SO-Werte auszugeben.
Gleiche Namen und Skalen allein belegen noch keine physische Checkpoint-Kompatibilität.

Die F3A-Dokumentation nennt für das SO-101-Paket `observation.images.scene` und
`observation.images.wrist`. Die gewünschten NexArm-Defaults bleiben `front`/`wrist`;
später Namen konfigurieren oder Upstreams `rename_map` verwenden, keine Namen
fest im Treiber verdrahten.

## 6. Ursprüngliche Fragen und freigegebene Entscheidungen

Die nachfolgenden ursprünglichen Fragen sind durch die ausdrücklichen Antworten
des Nutzers zur Implementierung freigegeben. Der jeweilige Befund bleibt zur
Nachvollziehbarkeit stehen; maßgeblich ist die Entscheidung unter jeder Frage.
Reale Messwerte und Hardwareabnahme bleiben offen, siehe Abschnitt 8.

### Q1 — Gradmodus: Richtung, Begrenzung und Quantisierung

U ignoriert `drive_mode` bei Gradwerten, obwohl hier eine manuell einstellbare
Richtung für jedes Gelenk verlangt ist. Soll das Plugin die gleiche Grad-Skalierung
mit expliziter Software-Vorzeichenumkehr verwenden? Das erfüllt die geforderte
Richtungsfunktion, ist aber eine bewusste Erweiterung gegenüber diesem U-Zweig.
Zusätzlich festlegen: U-`int()` oder bisheriges NexArm-`round()` beim Rückweg,
und Verhalten von Gradaktionen außerhalb der erfassten Grenzen. Keine implizite
Begrenzung ergänzen, die der Grad-Zweig von U selbst nicht vornimmt.
**Entschieden:** Grad-Skalierung `360/4095`, explizites Software-Vorzeichen
über `drive_mode`, Rückweg mit `round()`, Begrenzung auf kalibrierte Rohgrenzen.
Der Nullpunkt ist nach Q4 der gemessene `homing_offset`, nicht ein implizit
neu berechneter Min/Max-Mittelpunkt. Das sind bewusste NexArm-Erweiterungen.
`use_degrees=True` ist der anhand des F3A-Vertrags gewählte Default; die
Alternative RANGE_M100_100 bleibt explizit konfigurierbar. Evidenz in Abschnitt 8.

### Q2 — Leader/Follower-Koordinaten und Greiferabbildung

Die alte Funktion liefert bereits **Follower-Rohziele**, einschließlich fester
Schulterspiegelung und Greiferverstärkung. Unabhängig je Gerät auf Min/Max zu
normalisieren kann die feste Abbildung verändern; nachträglich nochmals zu
spiegeln oder das Richtungssignum zu verwenden kann sie doppelt anwenden.
Wie sollen die Leader-Kalibrierwerte die physisch gelesenen Rohpositionen und die
abgebildeten Follower-Ziele miteinander verknüpfen? Soll der Leader dafür die
Follower-Kalibrierung referenzieren, oder wird eine ausdrücklich definierte
Abbildung in den gemeinsam normierten Raum festgelegt?
Die Schulterformel `4096-pos` und der Greiferbereich `[1195,2833]` stehen fest;
die zusätzliche Greiferformel mit Faktor 4 darf nicht still durch eine andere
Endpunkt-Normalisierung ersetzt werden. Auch die Reihenfolge von Mapping und
manuellem Vorzeichen sowie der Umgang mit Sättigung müssen eindeutig sein.
**Entschieden:** Pflichtfeld `follower_calibration_path` am Leader verweist auf
die tatsächlich vom Follower benutzte JSON. Ablauf: Leader raw → unveränderte
feste Herstellerabbildung → Follower-Rohziele → Clipping und Normierung mit
Follower-Kalibrierung. Vorzeichen genau einmal dort. Die eigene Leader-Datei
dokumentiert seine Messung; ihre Vorzeichen werden nicht noch einmal angewendet.
Beide Dateien werden beim Reconnect geladen, Änderungen erfordern Neustart beider Geräte.

### Q3 — Torque beim Disconnect: Quelle, SO und alter Test widersprechen sich

H/O `config_nexarm_follower.py:41` setzt `disable_torque_on_disconnect=False`.
U-SO setzt `True`; H/O `tests/robots/test_nexarm_follower.py` erwartet ebenfalls
`True`, obwohl die getestete NexArm-Konfiguration `False` liefert.
Soll das bisherige Halten oder das Abschalten des Drehmoments Default sein?
**Entschieden:** `disable_torque_on_disconnect=False` bleibt Herstellerdefault.
Der neue Regressionstest erwartet explizit False und prüft die Bytefolge ohne
Torque-off beim normalen Disconnect. Ein optionales True wird separat getestet.
CMD 68 zum Verlassen der Bridge bleibt verpflichtend; tatsächliches Verhalten
der Firmware nach Bridge-Ausgang ist noch von Menschen zu bestätigen.

### Q4 — Kalibrierungsnullpunkt, Grenzübertritt und alte Platzhalterdateien

Der alte Offset `2048` ist nur ein gespeicherter Platzhalter; der NexArm-Treiber
verwendet oder programmiert ihn nicht. U setzt Homing in den Motoren.
Wie wird die gewünschte SO-101-Referenzpose am realen NexArm festgelegt und
`homing_offset` bei rein hostseitiger Kalibrierung interpretiert? Überschreitet
ein benutzter Bewegungsbereich den Encoderübergang `4095↔0`? Dann reichen einfache
Roh-Min/Max ohne festgelegten Umgang mit Wrap nicht aus.
Wie werden vorhandene pauschale Alt-JSONs von echten Messkalibrierungen unterschieden
und neu eingemessen, obwohl beide dasselbe Schema und erlaubte `drive_mode`-Werte haben?
Für den Greifer Messbereich innerhalb `[1195,2833]` und Bedeutung der Endpunkte
(offen/geschlossen) am Arm bestätigen; keine vermeintlichen Messwerte voraussetzen.
**Entschieden:** Zwei Messschritte: SO-101-Referenzpose lesen und als hostseitigen
Roh-Nullpunkt in `homing_offset` speichern, dann Bereiche beim manuellen Bewegen
aller Gelenke aufnehmen. Kein Schreiben von Servo-Offsets. Ein Sprung von mehr
als 2048 Ticks zwischen Messungen bricht als möglicher Wrap/Sampling-Sprung ab.
Es gibt keine automatische Wrap-Korrektur. Die vollständige alte Platzhaltersignatur
wird verworfen; ungültige/fehlende Felder ebenfalls. Follower-Greifergrenzen müssen
innerhalb `[1195,2833]` liegen, der Leader-Rohgreifer wird separat vermessen.
Min/Max, Referenzpose und offene Greiferseite bleiben menschliche Messaufgaben.

### Q5 — Kalibrierung: Torque und Connect ohne Freigabe für Aktionen

Der CLI ruft `connect(calibrate=False)` vor `calibrate()` auf. Der alte Follower
schaltet trotzdem in `configure()` Torque an. Für das manuelle Vermessen muss
Torque aus sein. Soll dieser Connect-Pfad durchgehend torque off bleiben und
erst ein kalibrierter normaler Betriebsstart Torque einschalten? Zeitpunkt des
Wiedereinschaltens nach Kalibrierung und Verhalten bei Abbruch festlegen.
Normierte Aktionen bleiben ohne gültige Kalibrierung in jedem Fall gesperrt.
**Entschieden:** `connect(calibrate=False)` ist durchgehend torque off, auch bei
vorhandener Kalibrierung. Normales Connect darf Torque nur bei gültigen Daten
aktivieren. Neue Kalibrierung, Wiederverwendung im Kalibrier-CLI und Abbruch
lassen Aktionen gesperrt; erst Reconnect gibt sie frei. Bei Abbruch: Torque-off,
Bridge-Ausgang, Port schließen. Vorherige JSON wird bei fehlgeschlagener Messung
nicht überschrieben; neue Dateien werden atomar ersetzt.

### Q6 — `send_action`: Zielwert oder gemessene Rückmeldung als Dataset-Aktion

H/O gibt nach CMD 97 die CMD-96-Messung zurück, U-SO dagegen den angewendeten
Zielwert. `lerobot-record` speichert diese Rückgabe als Aktion; Messwerte würden
somit Zielkommandos im Dataset ersetzen. Welche Semantik soll gelten?
Vorschlag zur Klärung: normalisierte tatsächlich gesendete Ziele zurückgeben,
Messwerte als Beobachtung führen. Separat entscheiden, ob der bisherige zusätzliche
CMD-96-Read nach jedem Write erhalten bleibt; sein Entfernen ändert das I/O-Timing.
**Entschieden:** Rückgabe sind erneut normierte tatsächlich geschriebene,
quantisierte und begrenzte Ziele. Readback wird nicht zum Dataset-Aktionswert.
`readback_after_write: bool = True` erhält den zusätzlichen CMD-96-Read und dessen
Timeout-Toleranz; False lässt ihn aus. Ob False am Arm sinnvoll ist, bleibt offen.

### Q7 — Zusätzliche Hold-/Homing-Bewegungen im aktuellen Rollout

Soll NexArm am neuen `supports_position_hold`-Vertrag teilnehmen? Das ist bei SO
aktiviert, im alten NexArm aber nicht vorhanden. Zudem setzt U
`RolloutConfig.return_to_initial_position=True` standardmäßig; die Hersteller-Doku
beschreibt ebenfalls Rückkehr, was keine Abnahme dieses Plugins ersetzt.
Für das Inferenzbeispiel explizit festlegen, ob diese automatische Bewegung gewünscht
ist. Kein Hold-Opt-in und keine zusätzliche Gerätebewegung aus dem SO-Code übernehmen,
bevor vollständige normalisierte Zielrückgaben und Verhalten vereinbart sind.

**Entschieden:** Kein Hold-Opt-in, beide Capability-Flags bleiben False.
Das Inferenzbeispiel setzt explizit `return_to_initial_position: false`.

### Q8 — Aktuelle Ports und Windows-Kameraformat

Welcher Satz ist aktuell: Follower/Leader `COM19/COM18`, `COM9/COM10` oder
`COM4/COM3`? Welche Kameraindizes gehören zu `front` und `wrist`, und ist `MJPG`
für beide Kameras weiterhin erforderlich? H und O unterscheiden sich in diesen
gerätewirksamen Parametern. Alle Ports bleiben bis zur menschlichen Zuordnung
Platzhalter; keine davon wird zur Prüfung geöffnet. Die Aufnahme-Artefakte in
`old/outputs/` ersetzen diese Bestätigung nicht. Neue Beispiele übernehmen erst
nach Klärung einen abweichenden Kameraformat-Default.

**Entschieden:** `COM19`/`COM18` und Indizes `1`/`2` bleiben ausdrücklich
kommentierte Platzhalter, die Menschen ermitteln. Windows-Beispiele verwenden
konfigurierbares MJPG für beide Kameras. Die alten COM9/COM10- oder COM4/COM3-Werte
werden nicht als aktuelle Zuordnung angenommen.

Weitere menschliche Abnahmewerte: sechs tatsächliche Bereiche und Richtungsvorzeichen,
SO-Referenzpose sowie für spätere Inferenz die genaue Checkpoint-/Prozessorrevision
mit passenden Einheiten und Kamera-Keys. Fehlende Werte werden nicht geschätzt.

## 7. Geplante Prüfung und Abnahme nach der Implementierung

Die vorhandenen Hersteller-Tests sind Referenzmaterial, keine bereits passende
Abnahmesuite: neben dem Torque-Widerspruch erwarten Robot-Tests rohe Werte und
Dummy-Kalibrierung. Neue Tests müssen den vereinbarten normierten Vertrag prüfen.

- Feste, unabhängig hergeleitete Bytes für CMD 96/97/98/68, inklusive CMD-96-Antwort,
  Little-Endian-Nutzdaten, korrekter und kurzer Leader-Prüfsumme sowie beschädigter,
  abgeschnittener und durch Debugtext gestörter Frames.
- Exaktes Schulter-Mapping samt Randwert `0→4095`; unveränderte Greiferabbildung
  und Sättigung gemäß der geklärten Q2-Entscheidung.
- Alle sechs Kanäle mit beiden Richtungen, beiden Körpermodi, Endpunkten und
  inneren Werten raw → LeRobot → raw. Erwartete Quantisierung nach Q1 festlegen;
  durch Clipping gesättigte Werte sind nicht beliebig invertierbar.
- JSON-Speichern/Laden, manuelle Richtungsänderung, unvollständige/ungültige
  Kalibrierung und Verbot von Aktionen ohne gültige Daten; Messdialog mit Mocks.
- Robot und Teleoperator über die echte Treiberlogik mit gemocktem
  `serial.Serial`: Connect/Read/Write/Disconnect, Torque-Sequenz, Bridge nur beim
  Follower, Timeouts und Bereinigung auch nach fehlgeschlagenem Kamera-Connect.
  Kein Test darf einen echten Port öffnen; Kameras ebenfalls mocken.
- Installiertes Plugin in frischem Prozess über Upstreams Scanner und Factories
  prüfen, CLI-Parsing für beide Typen und die drei YAMLs ohne Geräteverbindung
  validieren. Keine echten `calibrate`-/`teleoperate`-/`record`-Loops dafür starten.
- `uv run pytest` sowie Installation neben der exakten Git-Revision prüfen.
  Im ersten Dokumentationsschritt wurden diese Prüfungen nicht ausgeführt;
  die inzwischen durchgeführte Implementierungsprüfung ist in Abschnitt 9 dokumentiert.

Erst danach testen Menschen: Positionen torque off mit Hiwonders PC-Tool vergleichen,
kalibrieren und Vorzeichen prüfen, teleoperieren, zehn Episoden aufnehmen und im
Dataset-Visualizer kontrollieren. Das ist noch ausstehend.

## 8. Tatsächliche F3A-SO-101-Vertragsprüfung

Am 12.11.2026 mit dem vom Nutzer freigeschalteten HF-Zugang ausschließlich sieben
Vertragsdateien aus `black-forest-labs/flux-3-action-so101` heruntergeladen.
Alle lokalen Download-Metadaten nennen dieselbe Revision
**`e2584b2698e3b88368854976e354af87ec9893c6`**. Kein Modellgewicht, kein VAE und
kein Textencoder wurden angefordert oder geladen.

| Datei | Byte |
| --- | ---: |
| `config.json` | 2920 |
| `dataset_statistics.json` | 752 |
| `policy_preprocessor.json` | 1574 |
| `policy_postprocessor.json` | 536 |
| `policy_preprocessor_step_3_flux3_observation_history_normalizer.safetensors` | 360 |
| `policy_preprocessor_step_4_flux3_action_target_normalizer.safetensors` | 184 |
| `policy_postprocessor_step_0_flux3_action_history_unnormalizer.safetensors` | 184 |
| **Gesamt** | **6510** |

Reproduzierbarer lokaler Prüfer: `scripts/inspect_checkpoint_contract.py`.
`reference/contract_report.json` enthält alle SHA-256-Hashes, Dateigrößen und
vollständigen Quantile. Download-Aufruf mit exakter Revision steht in
`reference/README.md`; heruntergeladene Originale sind gitignored.

Das Skript liest die Safetensors ohne Policy-Initialisierung und bestätigt
**exakte Gleichheit** aller enthaltenen `state.q01/q99` bzw. `action.q01/q99`
mit `dataset_statistics.json`, sowohl im Observation-Normalizer als auch im
Action-Target-Normalizer und Action-Unnormalizer. `config.json` selbst enthält
`normalization_stats: null`: Die tatsächlichen Statistiken liegen in den
gespeicherten Prozessorzuständen. `normalization_mapping: IDENTITY` bedeutet hier
nicht fehlende Normalisierung; der History-Prozessor übernimmt sie.

Numerische Zusammenfassung (auf drei Nachkommastellen gerundet):

| Kanal | state q01 | state q99 | action q01 | action q99 |
| --- | ---: | ---: | ---: | ---: |
| shoulder_pan | -37.969 | 35.288 | -1.652 | 1.701 |
| shoulder_lift | -99.316 | 43.076 | -3.235 | 3.487 |
| elbow_flex | -45.780 | 90.308 | -3.147 | 3.307 |
| wrist_flex | 22.987 | 95.704 | -2.198 | 2.072 |
| wrist_roll | -68.712 | 17.753 | -1.708 | 1.699 |
| gripper | 0.450 | 40.324 | 0.000 | 40.733 |

**Ergebnis: Grad für die fünf Armachsen, 0..100 für den Greifer.**
Die Quantile allein beweisen das hier nicht: Keines der Zustandsquantile liegt
außerhalb ±100. Die vorgeschlagene Größenordnungsheuristik ist für diesen
Checkpoint daher nicht entscheidend. Die explizite Einheitenangabe in der
[offiziellen SO-101-Modellkarte, „Calibration and normalization“](https://huggingface.co/black-forest-labs/flux-3-action-so101#calibration-and-normalization)
nennt `use_degrees=True`, Grad um die Gelenkmitte und Greifer 0..100.
Diese Aussage plus die geprüften Config-/Prozessorverträge begründet den Modus;
er wurde nicht nur aus dem Default von `so_follower` geraten.

Die Config legt `action_representation: delta`, `delta_absolute_dims: [-1]`,
sechs Kanäle, 30 Hz und Kameras `scene`/`wrist` fest. Deshalb sind die ersten fünf
Aktionsquantile **Winkeldeltas**, keine absoluten Gelenkbereiche; der Greiferkanal
bleibt absolut. Der gepinnte Code in `processor_flux3.py` lädt diese eigenen
History-Quantile und integriert die Aktion anschließend. Das Plugin muss
Hardware-Beobachtungen und absolute Zielaktionen in Grad/Prozent liefern;
es implementiert keine zusätzliche F3A-Delta-/Statistiknormalisierung.

Die Modellkarte beschreibt Kalibrierung um die Mitte des Gelenkbereichs.
Unser explizit freigegebener gemessener Referenznullpunkt kann davon abweichen.
Menschen müssen die SO-Mittelpose und Richtungen am NexArm angleichen;
Einheitengleichheit ist kein Nachweis identischer Kinematik oder Zero-shot-Eignung.

## 9. Implementierungsstand und verbleibende Abnahme

- Eigenständige Distribution `lerobot_robot_nexarm`, exakter LeRobot-Git-Pin
  einschließlich `core_scripts`, optionales `cloud` mit `flux3` am gleichen Pin.
- Hersteller-Treiber als `src/lerobot_robot_nexarm/bus.py` **bytegleich** kopiert.
  SHA-256 beider Dateien:
  `d53a53ba1f61fa9584b203e25c30227a184a4de011b64d2ad4e0441b1c155b40`.
  Vom Formatter ausgenommen, keine Änderungen an Protokoll, Timing oder Mapping.
- Follower und Leader mit Host-Kalibrierung, Aktionssperre, ausdrücklich
  freigegebenen Normalisierungs-/Torque-/Readback-Entscheidungen implementiert.
  Leere Leader-Feedback-Features und fehlendes Hold-Opt-in bleiben erhalten.
- Windows-YAMLs und README einschließlich Ports/Kameras, Kalibrierungsrichtung,
  Modellvertrag, Bridge/Checksum/Port-busy/WSL und Pin-Bump vorhanden.
- `uv sync` installiert neben dem Plugin tatsächlich LeRobot `0.7.1` aus dem
  verlangten Git-Commit. Der Test prüft dessen `direct_url.json`, nicht nur eine
  nominelle Versionsnummer. Bei der Installation fehlte upstream ein LFS-Testbild;
  mit `GIT_LFS_SKIP_SMUDGE=1` wurde ausschließlich dessen Download übersprungen.
  Die drei schreibgeschützten Quellbäume wurden nicht verändert.
- Wheel-Bau erfolgreich: `dist/lerobot_robot_nexarm-0.1.0-py3-none-any.whl`.
  Installierte Metadaten enthalten tatsächlich `Name: lerobot_robot_nexarm`.
  Frischer Python-Prozess findet beide Configs über den unveränderten Upstream-
  Scanner und erstellt beide Geräte über die Factories ohne `connect()`.
  Alle drei YAMLs wurden gegen die echten CLI-Schemata am Pin geparst; beim
  Inferenzschema wird nur das Laden einer kleinen Policy-Config gemockt.
- Die vollständige hardwarefreie Testsuite besteht mit **109 Tests**; Ruff-Lint
  und Formatprüfung bestehen ebenfalls. Echte Serial-Aufrufe sind in den Tests
  standardmäßig gesperrt, die Gerätetests verwenden einen Byte-Stream-Mock.

**Offen sind ausschließlich die menschlichen Hardwarewerte und deren Abnahme:**
aktuelle COM-Ports/Kameraindizes, reale nicht-wrappende Gelenkbereiche, Referenzpose,
Greifer-offen/-geschlossen, `drive_mode` pro Gelenk und das tatsächliche Halten
beim Verlassen der Bridge. Ebenso ist das Abschalten des zusätzlichen Readbacks
erst nach Timing-Prüfung am Arm sinnvoll. Keine dieser Eigenschaften wurde mit
einem echten Gerät getestet oder als bestätigt ausgegeben.
