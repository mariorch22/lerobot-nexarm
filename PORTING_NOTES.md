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

## 10. Rückmeldung aus der menschlichen Einrichtung am 13.11.2026

Die lokale Teleoperate-YAML wurde vom Nutzer bereits auf Follower COM11 und
Leader COM12 geändert; diese Änderung bleibt erhalten. Der vorgelegte Log zeigt
eine Portöffnung auf COM11, dann einen Abbruch per KeyboardInterrupt im ersten
Kalibrierdialog. Es wurde noch keine Referenzposition gelesen und keine neue
Kalibrierung gespeichert. Der folgende Teleoperate-Versuch scheiterte deshalb
an der fehlenden `calibration/follower/follower.json`, bevor der Leader-Port
geöffnet wurde. Daraus folgt noch kein erfolgreicher CMD-96-Positionsvergleich.

Zusätzlich zeigt der Log trotz `--robot.cameras="{}"` weiterhin beide Kameras:
Der CLI-Override hat das vorhandene YAML-Dictionary am Pin nicht geleert.
Korrigiert durch eine separate `teleoperate_no_cameras.yaml` mit leerem Dictionary,
geprüft gegen das echte CLI-Schema einschließlich COM11/COM12-Overrides.
Keine Änderung am Upstream-Parser. Der Kalibrierdialog verweigert jetzt
nichtleere Eingaben an seinen ENTER-Bestätigungsprompts, damit hineinkopierte
Shell-Befehle keinen unbeabsichtigten Nullpunkt speichern. Die vorhandene
Fehlerbereinigung lässt dabei Torque aus und verlässt die Follower-Bridge.
Diese Änderungen werden ausschließlich mit Mocks geprüft; keine Agenten-Hardwarezugriffe.

## 11. F3A-Cloud-Einrichtung, Rauchtest und Erkenntnisse aus der Doku (13.11.2026)

Dieser Abschnitt dokumentiert die erste Inbetriebnahme von FLUX 3 Action (F3A) auf einer
gemieteten Cloud-GPU, einen Rauchtest mit Dummy-Eingaben und die daraus folgenden
Entscheidungen für Datensammlung, Training und Rollout. Der NexArm war an diesem Test
nicht beteiligt; alle Werte stammen aus der Cloud-Instanz.

### 11.1 Cloud-Instanz

| Eigenschaft | Wert |
| --- | --- |
| Anbieter | vast.ai |
| GPU | 1× NVIDIA RTX A6000, 49 140 MiB |
| Standort | Rumänien |
| Treiber / CUDA | 580.178.04 / CUDA 13.0 (abwärtskompatibel zu den cu128-Wheels) |
| Speicherplatz | 120 GB (`overlay`, `/`) |
| Image | `nvidia/cuda:12.8.1-cudnn-runtime-ubuntu22.04` |
| Kosten | ca. 0,51–0,56 $/h laufend, Speicher und Bandbreite separat |
| Instanz-ID | 60441095 |

Verwaltung über die vast.ai-Python-SDK mit kleinen Skripten (Suchen, Mieten, Status,
Löschen). Der API-Key liegt in einer gitignorierten `.env` bzw. über `vastai set api-key`
lokal, nie im Repo.

Erfahrungen aus der Einrichtung:

- Der Speicherplatz muss beim Mieten explizit gesetzt werden (`disk=120`). Die erste
  Instanz lief mit dem Default von 32 GB; das reicht für Umgebung plus Gewichte (ca. 25 GB)
  nicht und lässt sich nachträglich nicht vergrößern. Sie wurde gelöscht.
- Bei über die SDK erstellten Instanzen wurde der im Account hinterlegte SSH-Schlüssel
  nicht automatisch übernommen. Abhilfe: `vastai attach ssh <INSTANZ-ID> "<public key>"`.
- Hosts in Festlandchina meiden: Hugging Face ist dort nicht erreichbar. Ebenso meiden:
  CMP-170HX-Mining-Karten und umgebaute 48-GB-RTX-4090.
- Für Offline-Tests und Training ist der Standort egal. Für Live-Sessions mit dem Arm
  später einen Host in Asien wählen (Latenz zum Labor in Shenzhen).
- Auf der Instanz wird ein eigener Hugging-Face-Token nur mit Leserechten verwendet und
  nach dem Projekt gelöscht. Der zwischenzeitlich im Chat sichtbare vast.ai-API-Key
  wird erneuert.
- Nicht genutzte Instanzen stoppen (`vastai stop instance <ID>`): GPU-Kosten entfallen,
  Speicher wird weiter berechnet, Umgebung und Gewichte bleiben erhalten.

### 11.2 Installation auf der Instanz

Exakt nach der BFL-Anleitung „SO-101 with LeRobot“, aber am Projekt-Pin:

- LeRobot geklont und auf `2f05d8f64d62a865c368a9fdf0ba3d8423e28035` ausgecheckt
  (gleicher Pin wie das Plugin; nicht der jeweils neueste `main`).
- `uv venv --python 3.12`
- `torch==2.11.0`, `torchvision==0.26.0` aus dem cu128-Index
- `uv pip install -e '.[training,flux3,peft,diffusion]'`
- `natten==0.21.6+torch2110cu128`
- `ffmpeg` per apt

Prüfung: `2.11.0+cu128 True NVIDIA RTX A6000`.

Das eigenständige BFL-Repo `flux-action` wird für den LoRA-Weg nicht benötigt (siehe 11.6).

### 11.3 Modellpakete

| Paket | Revision | Umfang |
| --- | --- | --- |
| `black-forest-labs/flux-3-action-so101` | `c9e13b2aca6a0a472b3ea03fd90cff32d3e85849` | Policy, gespeicherte Prozessoren, Statistiken, ca. 13,9 GB |
| `black-forest-labs/flux-3-action-base` | `62878e2925e59b7a89ec14463ce89932624c490d` | nur `video_vae.safetensors` und `text_encoder/*`, ca. 11,4 GB |

Beide Repos sind zugangsbeschränkt und brauchen jeweils eine eigene Freigabe auf
Hugging Face. Die Freigabe für das SO-101-Paket gilt nicht automatisch für das Basismodell.

Ausgelesene Konfiguration des SO-101-Pakets:

```
camera_keys:    ['observation.images.scene', 'observation.images.wrist']
camera_layout:  side_by_side
fps:            30.0
chunk_size:     42
n_action_steps: 32
```

**Wichtiger Abgleich:** Die Vertragsprüfung in Abschnitt 8 lief gegen die Revision
`e2584b2698e3b88368854976e354af87ec9893c6`. Die BFL-Doku und der Download auf der
Instanz verwenden `c9e13b2aca6a0a472b3ea03fd90cff32d3e85849`. Bis zur erneuten Prüfung
ist offen, ob Einheiten, Gelenkreihenfolge und Quantile in beiden Revisionen identisch
sind. Siehe offene Punkte in 11.8.

### 11.4 Rauchtest

Skript `smoke_test.py` (ins Repo übernehmen unter `scripts/cloud/smoke_test.py`):

- Config aus `models/flux-3-action-so101` laden, `video_vae_id` und `text_encoder_id`
  auf die lokalen Dateien in `models/flux-3-action-base` setzen, `device=cuda`.
- `Flux3Policy.from_pretrained(...)` und `make_pre_post_processors(...)` wie im
  Inferenzbeispiel der Integrations-Doku.
- Dummy-Beobachtung: zwei Zufallsbilder 3×480×640 als `scene` und `wrist`,
  Zustand `[0, 0, 0, 0, 0, 50]` (fünf Gelenke in Grad, Greifer 50 %),
  Instruktion `"pick up the blue block"`.
- Drei Steuertakte mit `post(policy.select_action(pre(obs)))`, Zeitmessung mit
  `torch.cuda.synchronize()`, Spitzenspeicher mit `torch.cuda.max_memory_allocated()`.
- Danach Policy und Prozessoren zurücksetzen, Text-Encoder (Qwen) per
  `policy.frozen.text_encoder.cpu()` auf die CPU verschieben, Messung wiederholen.

Ergebnisse:

| Messgröße | Text-Encoder auf GPU | Text-Encoder auf CPU |
| --- | ---: | ---: |
| Laden (einmalig) | 83,1 s | – |
| Speicher nach dem Laden | 23,6 GiB | – |
| Takt 0 (Planung eines Chunks) | 2,764 s | 2,018 s |
| Takt 1 und 2 (aus der Warteschlange) | 0,005–0,006 s | 0,006 s |
| Spitzenspeicher während Inferenz | 24,2 GiB | 15,9 GiB |

Ausgegebene Aktionen (Auszug):

```
Takt 0: [-0.096,  0.260,  0.384, -0.144,  0.027, 44.288]
Takt 1: [-0.156,  0.673,  0.792, -0.124,  0.014, 43.073]
Takt 2: [-0.211,  1.229,  1.371,  0.063, -0.104, 39.871]
```

Bewertung:

- Die Pipeline aus Laden, Preprocessing, Policy und Postprocessing läuft fehlerfrei.
- Jede Aktion hat sechs Werte in der erwarteten Konvention: fünf Gelenke in Grad mit
  kleinen, gleichmäßigen Änderungen pro Takt, Greifer im Bereich von ca. 40–44 %.
- Beide Durchläufe liefern identische Werte. Die Vorhersage ist mit diesem Setup
  reproduzierbar, was spätere Vergleiche erleichtert.
- Takt 0 im ersten Durchlauf enthält zusätzlich das einmalige Kodieren der Instruktion
  und das Aufwärmen der GPU. Die realistische Planungszeit auf der A6000 liegt eher bei
  ca. 2 s pro Chunk.
- Die Bilder sind Zufallsrauschen. Die Aktionen sagen inhaltlich nichts über die
  Eignung für den NexArm aus.

Folgerungen:

- **Speicher:** Eine RTX 5090 mit 32 GB reicht, auch mit Text-Encoder auf der GPU.
  Eine Karte mit 24 GB ist beim Laden (23,6 GiB Spitze) zu knapp, da das Verschieben
  des Text-Encoders laut Doku den Spitzenwert beim Laden nicht senkt.
- **Ablauf am Arm (synchron):** ca. 1,07 s Bewegung (32 Aktionen bei 30 Hz), dann ca. 2 s
  Pause zum Neuplanen, bei Cloud-Betrieb zusätzlich die Netzwerklatenz. Für Tests
  ausreichend; schneller mit neuerer GPU (L40S, RTX 5090) und mit
  `--policy.compile_model=true` (noch nicht getestet).
- Mit einer lokalen RTX 5090 am Arm wäre der Standard-Runner `lerobot-rollout` direkt
  nutzbar und die Cloud-Brücke (11.5) entbehrlich.

### 11.5 Erkenntnisse aus der Integrations-Doku (`docs/source/flux3.mdx`)

**Inferenz und Zustand der Prozessoren**

- Pro Steuertakt läuft eine Beobachtung durch Preprocessor, `select_action` und
  Postprocessor. Die Policy plant intern einen Chunk und gibt pro Takt eine Aktion
  aus der Warteschlange zurück.
- Die Prozessoren sind zustandsbehaftet. Das Modell sagt für die fünf Armgelenke Deltas
  voraus (`action_representation: delta`), der Greifer bleibt absolut. Der Postprocessor
  integriert die Deltas zu absoluten Befehlen: Der erste Befehl einer Episode orientiert
  sich am gemessenen Zustand, jeder weitere am vorherigen Befehl.
- Policy und beide Prozessoren müssen an jeder Episodengrenze und nach manuellem
  Eingreifen zurückgesetzt werden. Der synchrone LeRobot-Runner macht das selbst.

**Kein asynchroner Betrieb**

- Laut Doku wird RTC bzw. asynchrone Inferenz für F3A nicht unterstützt. LeRobots
  eigener Policy-Server mit asynchroner Inferenz fällt damit für die Cloud-Anbindung aus.

**Konsequenz: Design der Cloud-Brücke (noch umzusetzen)**

- Eine Anfrage pro Steuertakt über das Internet ist zu langsam (30 Roundtrips pro
  Sekunde mit zwei Bildern).
- Die Doku beschreibt eine Chunk-Vorhersage mit `predict_action_chunk`, bei der der
  zuletzt gesendete Befehl als `observation.command_history` mitgegeben wird. Er dient
  als Anker für die Integration der Deltas, ohne in die Konditionierung des Modells
  einzugehen.
- Geplantes Design: Der lokale Client schickt nur beim Neuplanen Bilder, Gelenkwerte und
  den letzten gesendeten Befehl. Der Server führt Preprocessing, Chunk-Vorhersage und
  Postprocessing aus und liefert 32 absolute Befehle zurück. Der Client führt sie mit
  30 Hz aus. Der Server hält keinen Zustand zwischen Anfragen, was ihn robust gegen
  Verbindungsabbrüche macht.
- Vor der Umsetzung im gepinnten Code (`processor_flux3.py`) prüfen, ob der
  Postprocessor einen ganzen Chunk korrekt in einem Schritt integriert oder ob er
  schrittweise pro Aktion aufgerufen werden muss.

**Speicher**

- `policy.frozen.text_encoder.cpu()` verschiebt etwa 8,3 GiB auf die CPU. Nicht
  zwischengespeicherte Instruktionen werden dann langsamer kodiert, ihre Embeddings
  aber gecacht. Ein späteres `policy.to(...)` holt den Text-Encoder zurück auf die GPU.

### 11.6 Embodiment-Frage und Entscheidung

Der Doku-Abschnitt „Training other embodiments“ sagt: Für Roboter ohne eigenen
Checkpoint startet man vom Basismodell im eigenständigen Repo `flux-action` und definiert
eigene Action- und Conditioning-Heads, Kameralayout, Aktionsrepräsentation und
Normalisierung. Gleiche Dimensionen allein machen die Heads eines anderen Roboters nicht
wiederverwendbar.

Für den NexArm bedeutet das: Die Nutzung des SO-101-Checkpoints mit NexArm-Daten in
SO-101-Konvention ist nicht der offiziell vorgesehene Weg. Beim LoRA-Rezept werden die
Action- und Conditioning-Heads allerdings vollständig mittrainiert, was den Abstand
teilweise auffangen kann.

**Entscheidung:** Das Projekt verwendet ausschließlich LoRA auf dem SO-101-Checkpoint.
Volles Finetuning oder eigene Heads über `flux-action` sind nicht vorgesehen. Das
Risiko, dass der Embodiment-Abstand zu groß ist, ist bekannt. Es wird anhand des
Offline-Tests, des Zero-Shot-Tests und der ersten LoRA-Ergebnisse am Entscheidungspunkt
(ca. Mitte Dezember) bewertet. Als Rückfallebene für das RL-Projekt dient eine kleinere
Policy (z. B. ACT oder SmolVLA) mit derselben Infrastruktur.

### 11.7 Vorgaben für Datensammlung, Training und Rollout

**Kameras**

- Der Checkpoint erwartet `observation.images.scene` (feste Szenenkamera) und
  `observation.images.wrist` (Handgelenkkamera). Ältere Bezeichnungen wie `top` oder
  `front` beschreiben dieses Paket nicht.
- **Entscheidung:** Die feste Kamera heißt in den NexArm-YAMLs ab sofort `scene`
  statt `front`, und zwar vor der ersten Datenaufnahme. Damit entfällt eine spätere
  `rename_map`.
- Jedes Bild wird auf 256×256 verkleinert und zu einem 512×256-Bild zusammengesetzt:
  Szene links, Handgelenk rechts. Die 640×480-Bilder werden dabei auf ein Quadrat
  gestaucht; das ist unkritisch, solange Training und Einsatz identisch sind.
- Eine `rename_map` ändert nur Schlüssel und erkennt keine physisch vertauschte Kamera.
  Vor jeder Session das zusammengesetzte Bild prüfen. USB-Kabel der Kameras beschriften,
  weil sich Indizes beim Umstecken ändern können.
- Die Szenenkamera wird starr montiert und bewegt sich zwischen Datensammlung und
  Einsatz nicht. Ganzer Arbeitsbereich und Arm im Bild, konstantes Licht, kein
  Gegenlicht, keine Menschen im Bild.

**Datensatz**

- LeRobot-v3-Datensatz mit 30 Hz, sechs absoluten kommandierten Aktionen, sechs
  gemessenen Zustandswerten und einer Instruktion pro Episode.
- Gelenkreihenfolge: shoulder_pan, shoulder_lift, elbow_flex, wrist_flex, wrist_roll,
  gripper. Armgelenke in Grad, Greifer in Prozent. Das Plugin liefert genau das; keine
  zweite Normalisierung einbauen.
- Die Roboter-ID und Kalibrierung bei der Aufnahme müssen später beim Rollout identisch
  sein.
- Referenzgröße: BFL nutzte für „put the blue box into the container“ etwa 200
  teleoperierte Demos. Planung: 100–200 Demos pro Aufgabenvariante.
- Instruktionen auf Englisch, kurz und pro Aufgabe immer gleich formuliert.

**Training (Preset `examples/flux3/lora.json`)**

- Policy-Pfad auf `models/flux-3-action-so101`, Encoder per
  `--policy.video_vae_id` und `--policy.text_encoder_id` auf `models/flux-3-action-base`.
- Vor dem Start prüfen: Rang und Alpha 32, Lernraten 1e-4 (Adapter) und 5e-4 (Heads),
  BF16, Gradient Checkpointing, EMA-Decay 0,999.
- Die Normalisierungsstatistiken des Pakets bleiben fix. Andere Statistiken würden eine
  eigens vorbereitete Basis mit passenden Prozessoren erfordern.
- `steps` zählt Mikroschritte: Bei Batch 2 und Akkumulation 4 entsprechen
  10 000 Schritte nur 2 500 Optimizer-Updates.
- Neue Adapter entstehen über die `peft`-Sektion der Config. `--policy.use_peft=true`
  dient nur zum Laden eines vorhandenen Adapters.
- Fürs Training eine Karte mit 80 GB (A100) einplanen; Spitzenspeicher dort messen.
- Nach dem Training `pretrained_model` und `pretrained_model_ema` mit denselben
  Aufgaben, Startlagen und Einstellungen am Arm vergleichen. EMA ist nicht automatisch
  besser.

**Rollout**

- Synchroner Runner (`--strategy.type=base --inference.type=sync`), Modell und Arm auf
  derselben Maschine. Für die Cloud-GPU wird die Brücke aus 11.5 benötigt.
- Vor jedem Rollout beide Live-Kamerabilder prüfen. Koordinatenlimits in der
  Hiwonder-Software setzen, reduzierte Geschwindigkeit, eine Person am Netzschalter.

### 11.8 Offene Punkte und nächste Schritte

1. Kameranamen in `teleoperate.yaml`, `record.yaml` und `inference.yaml` von `front`
   auf `scene` umstellen, vor der ersten Aufnahme.
2. `scripts/inspect_checkpoint_contract.py` gegen die Revision
   `c9e13b2aca6a0a472b3ea03fd90cff32d3e85849` erneut ausführen und bestätigen, dass
   Einheiten, Gelenkreihenfolge und Quantile mit Abschnitt 8 übereinstimmen.
   Abweichungen hier dokumentieren.
3. Hardware-Abnahme fortsetzen (siehe Abschnitt 10): Kalibrierung mit SO-101-Referenzpose,
   Bereiche, Greiferrichtung, Vorzeichen pro Gelenk, Torque-Verhalten beim Verlassen der
   Bridge, Teleoperation, Timing der Schleife.
4. Zehn Test-Episoden aufnehmen, im Visualizer prüfen und als privaten Datensatz auf
   Hugging Face hochladen.
5. Offline-Test auf der Instanz: F3A auf den eigenen Episoden, vorhergesagte gegen
   tatsächliche Befehle. Erster belastbarer Hinweis auf den Embodiment-Abstand.
6. Cloud-Brücke nach 11.5 implementieren (Server auf der Instanz, Client am Laptop),
   nach Prüfung des Postprocessor-Verhaltens bei ganzen Chunks.
7. Zero-Shot-Test am echten Arm: „pick up the blue block“ gegen „pick up the red block“,
   je zehn Versuche, mit Sicherheitsvorkehrungen.
8. `--policy.compile_model=true` testen und die Planungszeit erneut messen.
9. `smoke_test.py` unter `scripts/cloud/` ins Repo übernehmen.
10. Klären, ob im Labor oder in der Gruppe eine RTX 5090 verfügbar ist. Damit entfiele
    die Cloud-Brücke für den Rollout.

## 12. Fehlender Bewegungsbereich bei der Follower-Kalibrierung

Der Nutzer meldet nach den Messabschnitten am 13.11.2026 einen Abbruch bei der
Bereichsvalidierung von `shoulder_pan`. Der Treiber begrenzt Rohwerte auf
0..4095 und der Recorder hält Min <= Max; in diesem Ablauf bedeutet der Fehler
deshalb Min == Max, also keine erfasste Wertänderung der Basis. Der konkrete
Rohwert wurde im ursprünglichen Log nicht angezeigt. Die Ursache (Gelenk nicht
bewegt, weiterhin blockiert, andere Port-/Armzuordnung oder unveränderte
Firmware-Rückmeldung) ist damit noch nicht geklärt. Keine gültige neue JSON
wurde gespeichert. Insbesondere wird Torque-off nicht von der Hardware bestätigt.

Der Dialog zeigt jetzt die Referenz-Rohwerte und während jedes Messabschnitts
`raw`, `min`, `max` des gewählten Gelenks, gedrosselt auf maximal fünf Anzeigen
pro Sekunde. Am Abschnittsende wird dessen Bereich ausgegeben. Bei Min == Max
wird sofort mit dem konkreten Wert abgebrochen, statt fünf weitere Gelenke
vermessen zu lassen. Die Validierungsfehlermeldung enthält ebenfalls den Wert.
Keine Grenzwerte geraten oder freigegeben, keine Protokollbefehle geändert;
Fehlerbereinigung und Kalibrierungspflicht bleiben bestehen. Prüfung ausschließlich
mit Mocks, keine Agentenverbindung zum realen Arm.

Nachfolgender menschlicher Versuch um 12:10 Uhr auf COM11: Referenz-Rohwerte
`[2040, 697, 1215, 2433, 672, 1192]`. Der Nutzer berichtet, die Basis von Hand
drehen zu können; der Messabschnitt liefert dennoch `shoulder_pan` Min=Max=2040.
Eine Serial-Antwort liegt damit vor, eine aktualisierte Messung des tatsächlich
bewegten Gelenks ist noch nicht nachgewiesen. Als nächstes die COM-Zuordnung
durch USB-Abziehen genau des bewegten Arms eindeutig feststellen; die bisherige
Zuordnung COM11=Follower / COM12=Leader war noch nicht physisch bestätigt.
Danach gegebenenfalls gegen Hiwonders Positionsanzeige vergleichen.

Zusätzliche Hardwarefrage: Der gelesene Greiferwert 1192 liegt drei Ticks unter
dem vorgegebenen Rohbereich `[1195,2833]`. Ist das eine Rückmeldetoleranz am
Endpunkt, eine andere Gerätezuteilung oder ein abweichender tatsächlicher Bereich?
Keine Toleranz, andere Grenze oder künstliche Kalibrierung implementieren,
bevor das am richtigen Arm geklärt ist. Die vorhandenen Schreibgrenzen bleiben bestehen.

Portzuordnung per menschlichem USB-Abziehtest: Nach Abziehen genau des zuvor
bewegten Arms verschwindet COM12; die reine Portenumeration zeigt nur noch COM11.
Der bewegte Arm ist damit COM12, während die bisherigen Kalibrierungsversuche
COM11 ausgelesen haben. Ob der abgezogene Arm der beabsichtigte Follower oder
Leader ist, muss noch bestätigt werden; die funktionalen Rollen werden aus
diesem Abziehtest allein nicht abgeleitet. Keine automatische Vertauschung der
Gerätekonfiguration und keine neue Serial-Verbindung durch den Agenten.

Der Nutzer bestätigt anschließend, dass der abgezogene Arm der Aufgabenarm und
nicht der von Hand geführte Steuerarm ist. Damit lautet die bestätigte Zuordnung:
**Follower COM12, Leader COM11**. Die lokale `teleoperate.yaml` sowie die
Aufrufbeispiele für den kamerafreien Test wurden entsprechend korrigiert.
Die früheren konstanten Werte und der Greiferwert 1192 kamen demnach vom Leader,
während der Follower bewegt wurde. Sie belegen keine Abweichung des
Follower-Greiferbereichs. Die Kalibrierung des tatsächlichen Followers auf COM12
und der Positionsvergleich stehen weiterhin aus.

Erster Versuch auf dem bestätigten Follower-Port COM12 um 12:16 Uhr:
Portöffnung erfolgreich, aber der erste CMD-96-Read nach Bridge-Eintritt und
Torque-off endet nach den vorhandenen drei Versuchen mit `No position reply`.
Es wurde kein Rohwert und keine neue Kalibrierung gespeichert. Die aktuelle
Enumeration sieht beide Ports weiterhin. Der Treiber ist erneut SHA-256-geprüft
bytegleich zur Herstellerfassung. Weder Öffnen des Ports noch das Senden von
CMD 68/98 bestätigt deren Umsetzung durch die Hardware. Als nächste menschliche
Prüfung externe Stromversorgung und anschließend gegebenenfalls Positionslesen
im Hiwonder-PC-Tool klären. Die Herstellerdokumentation nennt für Follower-Probleme
Portzuordnung, Unterstützung von CMD 68 in der Firmware und reguläres Aus-/Einschalten.
Firmware-/Bridge-Zustand und Stromversorgung sind hier noch nicht nachgewiesen;
keine Protokoll-, Timing- oder Firmwareänderung auf Verdacht.

Der Nutzer bestätigt externe Versorgung und eingeschalteten Arm. In den lokalen
NexArm-Unterlagen wurde kein zusätzlicher verpflichtender Modusschalter und
keine Firmwarequelle gefunden, die den Timeout erklärt. Gegenüber dem alten
normalen Betriebsablauf liegt der neue Kalibrierpfad vor dem Lesen bei Torque-off;
ob diese Firmware dabei Positionen meldet, ist weiterhin nicht hardwarebestätigt.
Es wird nicht auf Verdacht Torque-on ausprobiert oder ein Timeout erhöht.

`scripts/diagnose_nexarm.py` steht für einen menschlich gestarteten Test bereit:
gleicher Follower-Connect mit Bridge und Torque-off, dreimal die vorhandene
Positionslesefunktion, Ausgabe von TX und empfangenen Parserpuffern. Der originale
Treiber bleibt unverändert; der Diagnose-Subclass ergänzt ausschließlich Logs.
Keine Kalibrierungsdatei erforderlich, kein CMD 97 und kein Torque-on. Cleanup
verwendet den bestehenden Follower-Disconnect. Mocks prüfen Antwort und Timeout
sowie die Befehlsfolge. Der Agent führt keinen echten Diagnoseaufruf aus.

Ergebnis des menschlichen Diagnoselaufs auf COM12: korrekte TX-Frames für
CMD 68, Torque-off und insgesamt neun CMD-96-Anfragen; keine RX-Puffer während
der Lesefenster, dreimal Timeout, Cleanup mit Torque-off und Bridge-Ausgang.
Das ist bislang kein Prüfsummenbefund: Dem Parser wurden in den Lesefenstern
keine Bytes zugeführt. Außerhalb dieser Fenster bzw. vor einem Input-Buffer-Reset
ankommende Bytes wurden vom bisherigen Logger nicht vollständig erfasst.

Offene Hypothese: Der ESP32 könnte durch die Portöffnung neu starten oder
vorübergehend nicht empfangsbereit sein. Der Hersteller-Treiber wartet nur
100 ms, bevor der erste Bridge-Befehl gesendet wird; eine lange Pause am
späteren Kalibrierprompt würde einen vorher verlorenen Bridge-Befehl nicht nachholen.
Die [pySerial-FAQ](https://pyserial.readthedocs.io/en/latest/appendix.html#faq)
dokumentiert allgemein verlorene frühe Writes nach RTS-/DTR-bedingtem Reset;
[Espressif](https://docs.espressif.com/projects/esptool/en/latest/esp32/advanced-topics/boot-mode-selection.html#automatic-bootloader)
beschreibt entsprechende Steuerleitungen auch für CH340x. Das beweist nicht,
dass diese NexArm-Platine betroffen ist, und begründet keine Verdrahtungsänderung.

Als expliziter menschlicher Vergleichstest unterstützt nur das Diagnoseskript
`--startup-wait=2`: zusätzliche Pause nach Portöffnung vor CMD 68, Default 0
(bisheriges Verhalten). Serielle DTR-/RTS-Zustände werden nur angezeigt, nicht
gesetzt. Rahmen, Baudrate, Parser, Antworttimeouts und Torque-off bleiben gleich;
kein CMD 97, kein Torque-on. Mocks prüfen die Position der Pause vor dem ersten
Bridge-Write und beide Antwortfälle; reale Ursache und Ergebnis stehen noch aus.
Der Produktionstreiber bleibt bytegleich zur Herstellerfassung.

Der menschliche Vergleich mit `--startup-wait=2` zeigt ebenfalls neun erfolglose
CMD-96-Anfragen ohne RX-Puffer. Eine zusätzliche Startpause allein hat den Fehler
somit nicht behoben; das schließt etwa einen dauerhaft gehaltenen Reset über
Steuerleitungen oder andere Firmwarezustände nicht aus.

Zur Frage nach einem Portierungsfehler wurde erneut direkt mit `old/finsh`
verglichen: Der Serial-Treiber ist in old, hiwonder-fork und Plugin SHA-256-identisch,
aber die höhere Befehlsfolge unterscheidet sich absichtlich. Olds normaler
Follower-Betrieb sendet Torque-on, bevor er Positionswerte liest. Die neue, in Q5
freigegebene Kalibrierung liest erst nach Torque-off. Software-Normalisierung und
aktuelle HF-Policy-Prozessoren wurden beim vorliegenden Timeout noch nicht erreicht.
Die Mock-Serial-Implementierung antwortet standardmäßig unabhängig vom Torquezustand;
sie belegt daher keine Firmwareunterstützung für Lesen bei Torque-off.

Offen ist somit auch ein Zusammenhang mit der portierten Lifecycle-Sequenz.
Kein automatischer Wechsel des Kalibrierpfads auf Torque-on. Für einen expliziten
menschlichen Vergleich bietet nur das Diagnoseskript `--probe-before-torque-off`:
nach Bridge-Eintritt einmal vor dem Torque-off-Befehl lesen, dann den bestehenden
Torque-off-/Read-Ablauf fortsetzen. Anfangs-Torque ist unbekannt; kein Torque-on
und kein CMD 97 werden gesendet. Mocks simulieren gezielt Antworten vor Torque-off
und ausbleibende Antworten danach, damit diese beiden Befunde getrennt sichtbar sind.
Ohne dieses Flag bleibt der bisherige Diagnoseablauf erhalten. Reales Ergebnis offen.

Menschlicher Test mit `--startup-wait=2 --probe-before-torque-off`: bereits die
drei Reads vor dem neuen Torque-off-Befehl bleiben ohne RX; danach ebenfalls
neun Reads ohne RX, `reply received=False`, `Result: 0/3`. Damit ist der neue
Torque-off-Befehl in diesem Lauf nicht als alleinige Ursache belegt. Der
vorbestehende Hardware-Torque-Zustand war unbekannt, daher wurde damit nicht
Olds explizites Torque-on reproduziert. Ein Portierungsfehler ist durch den
negativen Test weiterhin nicht vollständig ausgeschlossen.

Als nächstes unabhängige Herstellerabfrage statt weiterer Protokolländerungen:
Die [offizielle NexArm-Anleitung](https://wiki.hiwonder.com/projects/NexArm/en/imitation-learning-version/docs/1_Getting_Started_NexArm.html)
beschreibt NexArm.exe mit `USB Serial`, `Read Firmware Version`, `Read Pos` und
einem HEX-RX/TX-Fenster. Auf COM12 nur diese Lesefunktionen prüfen lassen und
Antwort-/Fehlerausgabe vergleichen. Keine Zentrierung, Factory-Reset oder
Firmware-Neuprogrammierung aus dieser Anleitung ableiten. Das Vergleichsergebnis
steht aus; der Agent hat weiterhin keinen echten seriellen Port geöffnet.

Der Nutzer möchte die Diagnose weiter im Terminal durchführen. Der offizielle
Download für NexArm.exe wurde gefunden, aber weder heruntergeladen noch gestartet.
Nächster expliziter Diagnosevergleich: `--inactive-control-lines` fordert im
Diagnoseskript DTR=False und RTS=False bereits vor `open()` an. Die installierte
pySerial-Windows-Implementierung übernimmt diese Vorbelegung beim Öffnen; der
Hersteller-Treiber nutzt ansonsten die Defaults True/True. Die Hypothese eines
durch Steuerleitungen gehaltenen Resets ist allgemein von Espressif dokumentiert,
für diese Platine aber unbestätigt. OS-/Treiber-Glitches beim Öffnen bleiben möglich.

Nur der opt-in Diagnosepfad erzeugt Serial zunächst mit `port=None`, setzt die
beiden Zustände und öffnet anschließend den bestätigten Port. Baudrate, Frames,
Torque-off, Parser und Antworttimeouts bleiben gleich. Default und Produktion
verwenden weiter die ursprüngliche Portöffnung. Mocks prüfen, dass beide
Zustände vor dem Öffnen inaktiv sind, kein Torque-on und kein CMD 97 gesendet
werden und der Port beim Beenden geschlossen wird. Reales Ergebnis steht aus.

Der menschliche Lauf mit `--startup-wait=2 --inactive-control-lines` bleibt
ebenfalls ohne RX während aller neun CMD-96-Lesefenster, Ergebnis 0/3. Diese
Steuerleitungsvariante hat das Problem somit nicht behoben.

### Hersteller-Firmwarequelle als unabhängige Referenz

Aus dem offiziellen Ressourcenbereich wurden ausschließlich zur Quelltextprüfung
die Archive [Follower Nex_Arm.rar](https://drive.google.com/file/d/1f1zThhDJPDNiAFfawNGOMsocId3-73Nb/view)
und [Leader Nex_Arm.zip](https://drive.google.com/file/d/1ZFPaZdt81vEQezh8lLOJKDGZfeo7cZOk/view)
bezogen. Ausgewählte C++-Dateien liegen lokal im ignorierten Verzeichnis
`reference/vendor-firmware/`; nichts wurde ausgeführt, kompiliert oder geflasht.
Die installierte Firmwareversion des Arms ist dadurch weiterhin nicht bekannt.
Follower-Archiv SHA-256:
`da03881e33e98791901032948476d4ea6affcea1a2a4bbecc7fdc796cb42eb90`.
Leader-Archiv SHA-256:
`66fc508a678f5e02f05b1b8889e1776d55d087b4852893d802b2b5321ffb5a5b`.

Konkrete Befunde in der veröffentlichten Follower-Quelle:

- `system_task_handle.cpp:3458` initialisiert USB-Serial mit 1.000.000 Baud;
  `CommProtocol.cpp` bestätigt unseren Frameaufbau und die vollständige Prüfsumme.
  Baudrate und gesendeter CMD-68-Eintritt entsprechen somit dieser Quelle.
- `system_task_handle.cpp:2938` beantwortet CMD 68 mit Argument 1 zunächst
  explizit mit einem CMD-68-Frame und Argument 1, bevor die Bridge aktiviert wird.
  Die frühere Diagnoseausgabe, Bridge-Befehle hätten grundsätzlich kein ACK,
  war zu pauschal und wurde korrigiert: Der bestehende Treiber liest dieses
  mögliche ACK nicht aus. Aus den bisherigen Logs ist Bridge-Eintritt unbewiesen.
- `register_system_task` zeigt nach Serial-Initialisierung bereits 2,5 Sekunden
  Displayanimation sowie weitere Initialisierung. Zwei Sekunden Startpause
  schließen einen Reset-/Startzeitzusammenhang deshalb nicht aus.
- Im normalen Modus definiert `Global.h:16` CMD 1 als Firmware-Versionsabfrage.
  `system_task_handle.cpp:2177` liest die AT32-Version und antwortet mit sechs
  Bytes: ESP32 major/minor/patch und AT32 major/minor/patch. Anfangswerte für
  die AT32-Version sind 0.0.0; das bestätigt keine erfolgreiche AT32-Abfrage.
  Das reine Anfrageframe lautet `ff ff ff 02 01 fd`.
- **Offene Hardwarefrage:** `enter_lerobot_bridge_mode()` ersetzt den normalen
  USB-Callback. Der neue `bridge_usb_callback()` behandelt CMD 68 nicht lokal,
  sondern leitet unbekannte Befehle an AT32 weiter. Der normale CMD-68-Ausgang
  würde dagegen `ESP.restart()` auslösen. Ob die tatsächlich installierte
  Firmware unseren bisherigen Ausgangsbefehl wirksam verarbeitet, muss am Arm
  geklärt werden. Kein stiller Host-Protokoll-Fix und kein automatisches Flashen.

Nur das menschlich gestartete Diagnoseskript erhält `--controller-probe`:
Es öffnet den Transport ohne Robot-Lifecycle, sendet ausschließlich CMD 1 und
wartet bis zu drei Sekunden auf eine Firmwareantwort. Es sendet weder CMD 68
noch CMD 96/97/98. Bekannte Antwortformen mit drei oder sechs Bytes werden
angezeigt; andere Frames werden mitprotokolliert und nicht als Version ausgegeben.
Der Port wird auch bei Fehlern geschlossen. Der Test setzt einen normalen
Firmwarestart nach vollständigem Aus-/Einschalten einschließlich getrennter
USB-Versorgung voraus; er ersetzt keine fehlende Kalibrierung. Die explizite
Startpause von fünf Sekunden und inaktive Steuerleitungen bleiben auf diesen
Diagnoseaufruf beschränkt. Produktionstreiber, Normierung und Firmware bleiben
unverändert. Mocks prüfen das exakte Anfrageframe, Antwort mit vorangestelltem
Statusframe, Timeout, unbekannte Payload und Cleanup ohne weitere Befehle.
Reales Ergebnis der Firmwareabfrage steht aus.

Softwareprüfung dieser Ergänzung: 39 Diagnose-/Gerätetests mit gesperrten echten
Serial-Ports bestanden; Ruff-Lint und Formatprüfung bestanden. Der SHA-256 des
Produktionstreibers ist weiterhin unverändert. Die Tests bestätigen keine reale
Controllerantwort.

Der menschliche Firmwaretest auf COM12 mit `--controller-probe --startup-wait=5
--inactive-control-lines` sendet `ff ff ff 02 01 fd`, erhält im dreisekündigen
Lesefenster jedoch ebenfalls keine RX-Bytes und endet mit Timeout. Damit ist
auch über diesen vom Robot-Lifecycle unabhängigen Pfad keine Controllerantwort
bestätigt. Der Befund entsteht vor jeder Positionsnormalisierung; er identifiziert
weder einen Hardwaredefekt noch die installierte Firmware. Ob beim vorausgesetzten
vollständigen Neustart wirklich die normale Firmwareanzeige am Follower erscheint,
bleibt zu klären. Nächste Eingrenzung: sichtbarer Startzustand des Followers und
gegebenenfalls unabhängige Versionsabfrage im Herstellerprogramm, wie in der
offiziellen Anleitung unter USB Serial / System Settings beschrieben. Keine
weiteren Änderungen an Baudrate, Protokoll oder Firmware aus diesem Timeout ableiten.

## 13. Erneuter direkter Vergleich mit old wegen COM12-Timeout

Auf ausdrückliche Bitte des Nutzers wurden der tatsächliche Importpfad von old,
Treiber, Serial-Backend und die ausgeführten Follower-Befehlsfolgen erneut geprüft.
Alle Quelldateien in old, hiwonder-fork und upstream blieben unverändert; kein
echter serieller Port wurde geöffnet.

### Gesicherte Softwarebefunde

- `old/pyproject.toml`, `old/uv.lock` und die installierte LeRobot-`.pth` zeigen
  übereinstimmend auf `old/finsh/src`. Der andere Checkout `old/lerobot` ist nicht
  die Basis des bisherigen `uv run --locked`-Aufrufs.
- Motorbus, Follower, Leader und ihre beiden Config-Dateien sind zwischen
  `old/finsh` und `hiwonder-fork` jeweils bytegleich. Der Plugin-Motorbus ist
  ebenfalls bytegleich zu beiden Kopien, weiterhin SHA-256
  `d53a53ba1f61fa9584b203e25c30227a184a4de011b64d2ad4e0441b1c155b40`.
- Beide Projektumgebungen haben pySerial 3.5; auch `serial/serialwin32.py` ist
  bytegleich, SHA-256
  `17681ea9a650120c71db1aae9b8881301a40d38c47b34bb0da050e3f5bfbbe00`.
  Es wurde kein abweichendes Windows-Serial-Backend durch den Wechsel gefunden.
- Beide Teleoperation-Skripte verbinden zuerst den Leader, dann den Follower
  und lesen im normalen Loop zunächst die Follower-Beobachtung vor der Aktion.
  Die kamera-freie old-Konfiguration enthält keine weitere Hardwareinitialisierung.
  Ihre COM3/COM4-Werte sind alte Beispiele. Die zuletzt menschlich bestätigte
  Zuordnung für diesen Aufbau lautet Follower COM12, Leader COM11.

### Ausgeführter Vergleich mit denselben Mock-Antworten

Ein lokaler, ignorierter Prüfhelfer liegt in
`.uv-cache/test_old_transport_comparison.py`. Er führt den vollständigen originalen
old-Bustext und die unveränderten I/O-Methodenkörper des old-Followers mit einem
minimalen kalibrierten Objektkontext aus. Der alte LeRobot-Unterbau wird dabei
nicht geladen; seine Dateiverwaltung und die gesamte alte CLI sind somit nicht
Gegenstand dieses dynamischen Tests. Dies vermeidet Paketkollisionen und schreibt
keine Import-Caches in old. Das Plugin verwendet seine tatsächliche Follower-Klasse.
Alle Serial-Konstruktoren sind standardmäßig gesperrt und werden für die Prüfung
durch denselben Byte-Stream-Mock ersetzt; Testport ausschließlich `MOCK`.

Neun Vergleiche bestanden: Quell-/Backendgleichheit, normale Antwort, kurze
Firmware-Prüfsumme, fragmentierte Antwort, ungültige Prüfsumme, keine Antwort,
gleiche Rohziele mit Write/Readback, Kalibrier-Connect und ein ausdrücklich
hypothetischer Torque-abhängiger Mock. Der Aufruf zur lokalen Wiederholung lautet:

```powershell
uv run --no-sync --offline --cache-dir .uv-cache pytest -q .uv-cache/test_old_transport_comparison.py
```

Mit gültiger Kalibrierung stimmen Serial-Konstruktorargumente, TX-Bytes und die
explizit angeforderten Sleeps überein. Geprüft wurden 1.000.000 Baud und jeweils
0,05 Sekunden Read-/Write-Timeout; dies misst keine reale Windows-/Hardwarelatenz.
Bei gleichen physikalischen Zielen ist auch diese Folge identisch:

`68(on) -> 98(on) -> 96 -> 97 -> 96 -> 68(off)`.

Unterschiedliche Rückgabewerte von `send_action` sind die bereits freigegebene
Q6-Entscheidung: old liefert Readback-Rohwerte, das Plugin normierte gesendete
Ziele. Bei falscher Prüfsumme und ausbleibenden Antworten scheitern beide Pfade
mit denselben drei CMD-96-Versuchen. Kein Hinweis auf ein neu eingeführtes
Frame-/Checksum-/Baudratenproblem in der Portierung.

### Hardwarewirksamer Unterschied und weiterhin offene Ursache

| Pfad vor dem ersten Positionslesen | Befehlsfolge |
| --- | --- |
| old-Follower, auch bei `connect(calibrate=False)` | CMD 68 an, CMD 98 **an**, CMD 96 |
| Neues Plugin, gültige Kalibrierung im Normalbetrieb | CMD 68 an, CMD 98 **an**, CMD 96 |
| Neues Plugin, `connect(calibrate=False)` / Diagnose | CMD 68 an, CMD 98 **aus**, CMD 96 |

Die neue Kalibrierung schaltet zusätzlich vor der manuellen Erfassung nochmals
Torque aus. Diese Änderung folgt der ausdrücklichen Q5-Freigabe. Olds Kalibrierung
erfasste dagegen nichts, sondern speicherte nur die bekannten Platzhalter.

Der hypothetische Mock, der nur bei Torque-on antwortet, reproduziert einen
Erfolg für old und einen Timeout im neuen Kalibrierpfad. **Das belegt keine solche
Eigenschaft der realen Firmware.** Der frühere menschliche Read vor dem neuen
Torque-off-Befehl hatte unbekannten Anfangs-Torque und reproduzierte old ebenfalls
nicht vollständig. Auch die neue CMD-1-Versionsabfrage gehört nicht zum alten
LeRobot-Treiber; ihr Timeout beweist weder Firmwarekompatibilität noch einen Defekt.

Damit bleibt eine Ursache im geänderten Lifecycle möglich. Keine Änderung des
Kalibrierpfads auf Torque-on und kein Umgehen fehlender Kalibrierung auf Verdacht.
Der aussagekräftige nächste Hardwarevergleich ist der bekannte old-Aufruf mit
derselben bestätigten Portzuordnung und vergleichbarem Startzustand; dieser
normale Teleoperationsaufruf aktiviert Torque und kann den Arm bewegen und wird
ausschließlich vom Menschen ausgeführt:

```powershell
cd C:\Users\mario\robot\old
uv run --locked lerobot-teleoperate --config_path=teleoperate_no_cameras.yaml --robot.port=COM12 --teleop.port=COM11
```

Vor einem Vergleichslauf am Follower einen vollständigen Neustart einschließlich
getrennter USB-Versorgung durchführen, damit keine bestehende Bridge-Sitzung das
Ergebnis verfälscht. Wenn old damit aktuell antwortet, sind seine Logs ein neuer
Referenzbefund für die Lifecycle-Diagnose. Wenn old ebenfalls scheitert, ist das
weiterhin kein Beweis für einen Hardwaredefekt. Das reale Vergleichsergebnis
steht aus.

Zusätzlich bestand die vollständige aktuelle Plugin-Testsuite mit 137 Tests
(44,89 Sekunden). Zusammen mit den neun direkten Offline-Vergleichen wurden
146 Prüfungen bestanden. In diesem Arbeitsschritt wurden ausschließlich diese
Notizen und der ignorierte lokale Prüfhelfer geschrieben; keine Produktions-
oder Diagnosebefehlsfolge wurde verändert.

## 14. Freigegebene Rohwert-Teleoperation wie in old

Der Nutzer möchte ausdrücklich ohne die bisherige manuelle Kalibrierung wie
in old teleoperieren. Diese neuere Anweisung autorisiert für den unmittelbaren
Rohwert-Teleoperationstest einen eigenen Ablauf ohne Messdateien. Der bestehende
normierte Plugin-/F3A-Betrieb mit Kalibrierpflicht wird dadurch nicht ersetzt.

Olds `calibrate()` hat keine Grenzen oder Nullpunkte gemessen, sondern pauschale
Einträge mit Bereich 0..4095, Offset 2048 und `drive_mode=0` gespeichert. Seine
Teleoperation verwendete anschließend direkt Rohpositionen. Daher war damals
kein manueller Kalibrierdialog erforderlich. Diese Platzhalter eignen sich
nicht als gemessene SO-101-Referenz für den F3A-Checkpoint.

Implementiert wird `scripts/teleoperate_raw.py`, ausschließlich für menschlich
gestartete Teleoperation. Das Skript verwendet den bereits bytegleich übernommenen
Hersteller-Motorbus und die vorhandene feste Mappingfunktion. Es lädt keinen
alten Checkout und kopiert keine Experimente aus old. Keine Änderungen am
gepinnten Upstream, Motorbus, normierten Robot-/Teleoperator-Plugin oder Lockfile.
Ein eigener Rohwertablauf verhindert, dass das Standard-Inferenz- oder
Recording-Beispiel durch ein verstecktes Skip-Calibration-Flag Rohwerte erhält.

Übernommener Hardwareablauf aus old ohne Kameras:

1. Leader öffnen und Torque-off senden.
2. Follower öffnen, CMD 68 mit Argument 1 und anschließend Torque-on senden.
3. Pro Schleifendurchlauf zuerst Follower-Positionen, dann Leader-Positionen lesen.
4. Schulterspiegelung `4096-pos`, Greifer `2833+(pos-2048)*4` mit Begrenzung
   1195..2833 sowie allgemeine Rohwertbegrenzung 0..4095 unverändert anwenden.
5. CMD 97 senden und wie old anschließend CMD 96 lesen. Ein Timeout ausschließlich
   dieses zusätzlichen Readbacks wird wie im alten `send_action` toleriert.
6. Beim Ende CMD 68 mit Argument 0 senden und beide Ports schließen. Entsprechend
   dem Herstellerdefault kein zusätzlicher Follower-Torque-off beim Disconnect.

Die Schleife läuft mit bestmöglich 30 Hz; `--fps` und eine optionale `--duration`
sind einstellbar. Dies ist keine Zusicherung identischer Windows-Laufzeiten.
Beide Positionsabfragen müssen vor dem ersten Ziel erfolgreich sein. Fehler
beim anfänglichen Lesen enthalten Rolle und Port und beenden den Ablauf ohne
Positionsziel. Cleanup erfolgt auch bei Strg+C und teilweise fehlgeschlagenem
Bridge-Eintritt. Doppelte/leere Ports und ungültige Zeit-/Frequenzwerte werden
vor jeder Portöffnung abgelehnt. Keine Kalibrierdateien werden gelesen oder
geschrieben; keine Platzhalter werden als gültige Normierung ausgegeben.

Menschlicher Start im neuen Repo, nach Prüfung der Portzuordnung und freiem
Arbeitsbereich; dieser Aufruf aktiviert Torque und kann den Arm bewegen:

```powershell
uv run --locked python scripts/teleoperate_raw.py --follower-port=COM12 --leader-port=COM11
```

Das Skript ist ein eigener Ablauf für direkte Teleoperation; es zeichnet keine
Datasets auf und lädt keine Policy. Für die F3A-Standard-CLIs bleiben die
Grad-/Prozent-Normierung und deren Messkalibrierung erforderlich. Ob der reale
COM12-Timeout durch den Wechsel auf die alte Torque-on-Startsequenz behoben wird,
ist weiterhin offen. Der Agent öffnet auch für diesen Test keinen echten Port.

Prüfergebnis: vollständige Suite **151 bestanden**, davon 14 neue Prüfungen für
den Rohwertablauf. Zwei getrennte Mock-Ports prüfen die alte Start-/Read-/Write-
Reihenfolge, konkrete Schulter-/Greifer-Rohziele, zusätzliches Readback und dessen
Timeout, frühe Readfehler ohne Positionsziele, Strg+C, teilweise fehlgeschlagenen
Bridge-Eintritt sowie Argumentfehler vor jeder Portöffnung. Die optionale
Laufzeitgrenze verwendet einen absoluten monotonen Endzeitpunkt. Ruff-Lint,
Formatprüfung und `git diff --check` bestanden. Der Produktionstreiber bleibt
bytegleich; ein realer Hardwareerfolg wird aus den Mocks nicht abgeleitet.

## 15. Aktuelle Portzuordnung laut Nutzer

Die neue explizite Zuordnung lautet **Follower COM13, Leader COM14**. Sie ersetzt
für aktuelle Startbefehle die vorherigen COM12/COM11-Werte und COM19/COM18-
Platzhalter. Alle vier NexArm-Beispielkonfigurationen, die aktuellen README-
Befehle, CLI-Hilfebeispiele und der bestehende Parser-Test wurden entsprechend
angepasst. Historische Diagnosebefunde weiter oben behalten ihre damaligen Ports.
Die Zuordnung wurde vom Nutzer mitgeteilt; der Agent hat keinen Port geöffnet.

### Ergebnis des menschlichen Rohwert-Teleoperationstests

Der Nutzer startete `teleoperate_raw.py --follower-port=COM13 --leader-port=COM14`.
Nach gesendetem Follower-Torque-on endet bereits die erste Positionsabfrage mit
`Follower on COM13: No position reply from NexArm`. Damit behebt das Überspringen
der Kalibrierung zusammen mit der alten Torque-on-Startfolge den Timeout in
diesem Lauf nicht. Der tatsächliche Torque- und Bridge-Zustand ist weiter nicht
bestätigt. Laut Ablauf wurde kein CMD-97-Positionsziel gesendet; der Leader wurde
geöffnet, aber seine Positionsabfrage noch nicht erreicht.

Ein Problem ausschließlich durch den Kalibrierdialog erklärt diesen Befund
nicht. Ein Portierungsproblem insgesamt oder eine Hardware-/Firmwareursache ist
dadurch weder bewiesen noch ausgeschlossen. Weiterhin fehlt ein aktueller
menschlicher Gegenlauf mit der originalen old-Umgebung auf denselben Ports:

```powershell
cd C:\Users\mario\robot\old
uv run --locked lerobot-teleoperate --config_path=teleoperate_no_cameras.yaml --robot.port=COM13 --teleop.port=COM14
```

Wegen des unbestätigten Bridge-Ausgangs vor diesem Vergleich einen vollständigen
Follower-Neustart einschließlich getrennter USB-Versorgung vorsehen. Dieser
normale Teleoperationsaufruf kann den Arm bewegen. Keine weitere Protokoll-,
Baudraten- oder Timeoutänderung ohne neuen Vergleichsbefund.

Auf den anschließenden ausdrücklichen Wunsch des Nutzers wurde auch
`old/teleoperate_no_cameras.yaml` direkt auf Follower COM13 und Leader COM14
gesetzt. Diese konkrete Konfigurationsänderung ist die vom Nutzer angeforderte
Ausnahme zur bisherigen Read-only-Behandlung von old; seine Treiber und übrigen
Quelldateien bleiben unverändert. Für den Gegenlauf sind damit keine Port-Overrides
mehr nötig. `uv run --directory C:\Users\mario\robot\old --locked
lerobot-teleoperate --config_path=teleoperate_no_cameras.yaml` wählt unabhängig
vom aktuellen Shell-Ordner die alte Umgebung und deren Konfigurationsdatei.
Der Agent hat den Hardwareaufruf nicht ausgeführt.

### Originales old scheitert ebenfalls beim Follower-Lesen

Der Nutzer führte den Gegenlauf am 13.11.2026 um 15:43:50 mit `uv run
--directory C:\Users\mario\robot\old --locked lerobot-teleoperate
--config_path=teleoperate_no_cameras.yaml` aus. Der Trace bestätigt ausdrücklich
`old/.venv` und `old/finsh/src`, Follower COM13 und Leader COM14. Beide Ports
werden geöffnet; anschließend scheitert `robot.get_observation()` in old an
`read_positions()` mit `No position reply from NexArm`. Cleanup schließt beide
Ports. Das Lesen der Leader-Positionen und das erste Positionsziel werden laut
altem Loop noch nicht erreicht.

Damit tritt derselbe Follower-Lesefehler auch ohne die neue Portierung auf. Die
Logmeldung `connected` bestätigt nur das Öffnen des seriellen Ports und das
Absenden der Initialisierung, keine erfolgreiche Bridge-/Torque-Antwort. Ein
Problem speziell mit der neuen Gradnormierung oder der Kalibrierpflicht erklärt
diesen alten Lauf nicht. Die gemeinsame Transport-/Firmware-/Hardwareursache
bleibt offen; auch der unveränderte alte Treiber könnte mit der installierten
Firmware inkompatibel sein. Ein Defekt oder eine konkrete falsche Verdrahtung
ist durch den Timeout nicht bewiesen.

Nächste Hardwareeingrenzung: sichtbare normale Startanzeige und Anschlüsse des
Followers prüfen. Die offizielle Anleitung nennt das Originalnetzteil, den
eingeschalteten Netzschalter und das USB-Type-C-Datenkabel zum Controller. Für
die genaue Verkabelung verweist sie auf das Video unter 2.3.2 Wiring Instructions.
Ein Foto der tatsächlich belegten Controlleranschlüsse plus Displayzustand ist
noch nicht vorhanden. Keine weiteren Änderungen am Treiber aus diesem Log ableiten.

Der Nutzer berichtet anschließend, dass old wieder funktioniert. Welche
zwischenzeitliche Änderung an Anschluss, Versorgung oder Firmwarezustand den
Erfolg erklärt, ist nicht bekannt. Für den direkten nächsten Vergleich old
mit Strg+C beenden, damit die Ports frei sind, und das neue Rohwert-Skript mit
Follower COM13, Leader COM14 und `--duration=10` menschlich starten. Dabei ist
keine Kalibrierung erforderlich; der Agent führt den Hardwaretest nicht aus.

Der Nutzer bestätigt den anschließenden Zehn-Sekunden-Lauf des neuen
`teleoperate_raw.py` mit Follower COM13 und Leader COM14 als erfolgreich
("geht super"). Damit ist die direkte Rohwert-Teleoperation mit dem übernommenen
Herstellerablauf im neuen Repo menschlich am Arm bestätigt. Welche vorherige
Änderung die Timeouts behoben hat, ist weiterhin unbekannt; daraus folgt keine
Freigabe für spekulative Änderungen an Baudrate, Startzeiten oder Protokoll.
Die Abnahme des normierten Plugin-Betriebs, der gemessenen Kalibrierung,
Richtungsvorzeichen und des Recordings bleibt separat offen.

### Positionslesen nach Torque-off erfolgreich

Der Nutzer führte danach die Standarddiagnose auf COM13 ohne zusätzliche
Startpause und mit unveränderten DTR/RTS-Zuständen True/True aus. Nach CMD 68 an
und CMD 98 aus wurden drei gültige CMD-96-Antworten empfangen: zweimal
`[2024, 3304, 1613, 2921, 1074, 1195]`, anschließend
`[2024, 3304, 1613, 2921, 1074, 1196]`. Ergebnis **3/3**. Cleanup sendete erneut
Torque-off und den Bridge-Ausgang. Kein Positionsziel wurde gesendet.

Damit sind erfolgreiche Positionsantworten auch nach dem Torque-off-Befehl
am aktuellen Aufbau nachgewiesen. Die frühere Vermutung, dass dieser Befehl
generell sämtliche Positionsantworten verhindert, erklärt diesen aktuellen
Befund nicht. Ein Torque-ACK oder eine Prüfung der tatsächlichen manuellen
Beweglichkeit wurde weiterhin nicht gemeldet. Die Werte sind Momentaufnahmen,
keine gemessenen Grenzen oder Nullpunkte; 1195/1196 bestätigt für diesen Lauf
lediglich Greiferwerte am bekannten unteren Rohwertende.

Nächster menschlicher Schritt ist die Follower-Kalibrierung mit explizitem
Projektpfad und COM13. Vor ENTER am ersten Prompt muss die SO-Referenzpose am
NexArm abgeglichen werden; die aktuelle Diagnosepose darf nicht ungeprüft als
Nullpunkt übernommen werden. Die gepinnte SOFollower-Vorlage in
`lerobot/src/lerobot/robots/so_follower/so_follower.py`, `_HOMING_POSITION_DIAGRAM`,
zeigt einen senkrechten Oberarm und waagerechten Unterarm. Die Übertragung auf
den realen NexArm sowie Handgelenk-/Basisrichtung und Vorzeichen bleiben vor Ort
zu prüfen. Nach der Nullpunktaufnahme folgen erst die manuellen Bewegungsbereiche.

### Beweglichkeit bestätigt, Abbruch wegen Greifer-Sprung während Basisaufnahme

Der Nutzer korrigiert die vorherige Meldung über blockierte Gelenke: Manuelles
Bewegen funktioniert im laufenden Kalibrierdialog. Während `shoulder_pan`
aufgenommen wird, zeigt die Basis mindestens `min=2053, max=3465`. Am
13.11.2026 um 16:02:44 bricht die Kalibrierung jedoch mit einer vom **gripper**
gemeldeten Diskontinuität ab. Die bisherige Fehlermeldung enthielt die beiden
auslösenden Greiferwerte nicht. Somit sind ein tatsächlicher Encoderübergang,
ein einzelner unplausibler Messwert oder eine andere Abtastdiskontinuität nicht
unterscheidbar. Kein Schluss, dass die Basis zu schnell bewegt wurde.

Die vorhandene Routine überwacht wie vereinbart alle sechs Achsen. Deshalb
kann ein anderes Gelenk als die gerade genannte Aufnahmeachse den Abbruch
auslösen. Ein Sprung von mehr als 2048 Ticks ist innerhalb des festgelegten
Follower-Greiferbereichs 1195..2833 nicht möglich; mindestens ein Wert wäre dann
außerhalb dieses Bereichs. Die tatsächlichen Werte fehlen aber im Nutzerlog.
Diese Erkenntnis rechtfertigt weder stilles Verwerfen einer Antwort noch
Clipping, Entwrappen, einen höheren Schwellenwert oder einen Firmware-Fix.

Ergänzt wurde ausschließlich die Diagnose: Der Abbruch nennt nun vorherigen und
aktuellen Rohwert, vorzeichenbehaftete Differenz und beide vollständigen
Sechser-Messvektoren. Vor dem Cleanup wird die laufende Statuszeile abgeschlossen.
Die >2048-Regel, Überwachung aller Gelenke, Abbruch ohne Speichern, Torque-off-
Kalibrierung und der Motorbus bleiben unverändert. Tests prüfen Greifersprünge
in beiden Richtungen und den Abbruch mitten in der Basisaufnahme. Ein erneuter
menschlicher Lauf soll bei Wiederholung die fehlenden Werte liefern; bei einem
erneuten solchen Fehler keine weiteren kompletten Kalibrierungsversuche ohne
Auswertung des konkreten Sprungs.

Der davor angesprochene Kamera-/Readback-Timingvergleich bleibt offen. Der
gepinnt gelesene Standard-CLI hat eine Live-Schleifenzeit und einen CycleTimer-
Abschlussbericht; sein Code-Default ist 60 Hz, unsere YAML setzt bereits 30 Hz.
Das separate Rohwertskript hat diese Kamera-/Timingoptionen bisher nicht. Es
wurden weder Kameraindizes geändert noch `readback_after_write` ohne Messung
dauerhaft ausgeschaltet. Die normale Follower-/Leader-Kalibrierung ist noch
nicht abgeschlossen.

Prüfung der erweiterten Sprungdiagnose: 85 Kalibrierungs-/Gerätetests bestanden,
Ruff und `git diff --check` bestanden. Der Motorbus bleibt SHA-256-identisch zur
Herstellerfassung. Die neu getesteten Grenzsprünge sind synthetische Fälle und
keine nachträgliche Rekonstruktion des unbekannten tatsächlichen Greiferwerts.

### Kamera-Teleoperation aus dem Fork übernehmen

Auftrag vom 13.11.2026: Kamera-Teleoperation aus dem vorhandenen Herstellerfork
in dieses Repo übernehmen und an den aktuellen LeRobot-Pin anpassen. Als Quelle
dienen `hiwonder-fork/src/lerobot/scripts/lerobot_teleoperate.py`, der dortige
NexArm-Follower und `examples/nexarm/teleoperate.yaml`. Das vorhandene
`scripts/teleoperate_raw.py` wird dafür um optionale Kameras erweitert; so ist
der menschlich bestätigte Rohwertbetrieb auch vor Abschluss der Kalibrierung
mit Bildern nutzbar. Die Kalibrierungsanforderung des normalen Plugins bleibt bestehen.

Umsetzungsplan/API-Abgleich:

- Kamera-Konfiguration über `--camera-config` aus `robot.cameras` einer vorhandenen
  Teleoperations-YAML lesen und gegen die gepinnten OpenCV-Dataclasses prüfen.
  Ports und Kalibrierungsfelder dieser YAML werden im Rohwertskript nicht übernommen.
- Kamera-Factory am Pin aus `lerobot.cameras` verwenden. Wie im Fork zuerst
  `read_latest()`, bei veraltetem Bild `async_read(timeout_ms=2000)` aufrufen.
- Rerun über die aktuellen Visualisierungsfunktionen anbinden. Bei angegebenen
  Kameras die Anzeige standardmäßig aktivieren; `--no-display-data` erlaubt den
  Betrieb ohne Viewer. Die angezeigten Gelenkwerte bleiben Encoder-Rohwerte.
- Kameras und Viewer vor dem Öffnen der Serial-Ports vorbereiten; beim Abbruch
  auch teilweise verbundene Kameras freigeben. Mit Kamera-/Serial-Mocks prüfen,
  einschließlich Kameraausfall und unverändertem Motor-Mapping/Readback.

Es gibt keine neue Abweichung am Motorprotokoll und keine geänderte Kamera-
Indexzuordnung. `front=1`, `wrist=2`, 640×480/30 fps und MJPG bleiben die bereits
freigegebenen, vom Menschen am Aufbau zu prüfenden Beispielwerte. Hardwaretests
werden weiterhin ausschließlich von Menschen ausgeführt.

Umgesetzt im bestehenden Rohwertskript und in der README dokumentiert. Die
36 gezielten Rohwert-/Kameratests prüfen unter anderem echte YAML-Decodierung,
frei wählbare Namen/Indizes, Rerun-Ausgabe mit Rohwerten, BGR→RGB, Windows-
Fallback, Betrieb ohne Viewer sowie Cleanup bei Kamera-/Serial-Fehlern und
Strg+C. Kamera-Warmup-Fehler öffnen keinen Serial-Port. Die unveränderte
Motorbefehlsfolge einschließlich Readback wird auch mit Kameras geprüft.

Abschlussprüfung: gesamte Suite **185 Tests bestanden**, Ruff-Lint und
Formatprüfung bestanden, `git diff --check` bestanden. CLI-Hilfe ohne
Hardwarezugriff geprüft. Der Motorbus ist weiterhin SHA-256-identisch zur
Herstellerquelle. Die tatsächliche Kamerazuordnung und Bildrate sind noch
am Aufbau durch einen Menschen zu prüfen.

Ergänzung zur Frage nach realen FPS: Im Rohwertskript eine optionale
`--show-fps`-Terminalanzeige ergänzen. Abgeschlossene Teleoperationsdurchläufe
über monotone verstrichene Zeit messen, einschließlich FPS-Begrenzung, Serial,
Kameraabfrage und Rerun; einmal pro Sekunde anzeigen und beim Beenden eine
Gesamtrate ausgeben. Das ist die erreichte Schleifenrate, keine Messung der
unabhängigen Sensor-Bildrate. Kein zusätzlicher Kameraread und keine Änderung
der Motorbefehle. Mit künstlich verzögerter Kommunikation und begrenzten
Durchläufen ohne Hardware prüfen.

Umgesetzt: `Measured FPS`, mittlere `loop`-/`work`-Zeiten in Millisekunden und
Sollrate einmal pro Sekunde; `Overall FPS` am Ende. Die Gesamtmessung endet
vor dem Serial-/Kamera-Cleanup. Tests bestätigen 5 FPS bei einer Begrenzung
auf 5 sowie tatsächlich 10 FPS bei 100 ms künstlicher I/O-Zeit trotz Sollrate
30. Kurze Läufe erhalten ebenfalls den Abschlusswert. Prüfung: **190 Tests
bestanden**, Ruff-Lint/Format und `git diff --check` bestanden. Keine Hardware
geöffnet; die Sensor-Bildrate bleibt damit weiterhin ungemessen.

Logprüfung danach: Der menschliche Lauf zeigt 25..31 gemeldete FPS bei Soll
30, etwa 24..30 ms Arbeitszeit, Rerun-Eviction am 1-GiB-Proxy-Limit und später
einen gRPC-Transportfehler. Zwei lokale Softwarebefunde sind reproduzierbar:
Python 3.12.10 verwendet hier für `monotonic()` GetTickCount64 mit 0,015625 s
Auflösung; `perf_counter()` verwendet QueryPerformanceCounter mit 0,0000001 s
Auflösung. Außerdem setzt der gepinnte Upstream-Bildlogger `static=True` und
komprimiert Bilder standardmäßig nicht. Zwei RGB-Bilder 640×480 erzeugen bei
30 Hz bereits ca. 55 MB/s reine Bilddaten. Das erklärt schnellen Speicherdruck,
beweist aber nicht die Ursache des nachfolgenden Transportabbruchs.

Korrekturplan: Nur die Zeitbasis des Rohwertskripts auf `perf_counter()`
umstellen, einschließlich FPS-Begrenzung und Gesamtrate. Den Rerun-Livepfad
lokal im Plugin implementieren: Bilder mit JPEG-Qualität 80 auf einer expliziten
Zeitachse als zeitabhängige Daten loggen, Gelenkwerte ebenso zeitabhängig und
das Kamera-/Kurvenlayout erhalten. Upstream, Serial-Protokoll, Mapping und
Readback bleiben unverändert. Regression mit grob aufgelöster simulierter
Windows-Uhr sowie Rerun-SDK-Tests ohne Viewerstart oder Hardware ergänzen.
Der endliche Rerun-Historienpuffer darf weiterhin alte Daten verwerfen; eine
Behebung des konkreten Transportfehlers wird ohne erneuten Hardwarelauf nicht
behauptet.

Umgesetzt mit `RawTeleopViewer` in `src/lerobot_robot_nexarm/visualization.py`.
Die Vorschau erhält weiterhin separate Kamerabilder und Rohwertkurven; Bilder
und Skalare werden mit `static=False` auf `teleop_time` geloggt. JPEG betrifft
ausschließlich die Anzeige. Die FPS-Regression simuliert eine 15,625-ms-Uhr
neben einer präzisen Uhr und prüft korrekte 30 FPS bei 25 ms Arbeitszeit.
Weitere Tests nutzen echte SDK-Archetypen und JPEG-Kodierung bei gemockten
Logging-/Verbindungsfunktionen und prüfen das Cleanup nach Layoutfehlern.
Abschluss: **195 Tests bestanden**, Ruff-Lint/Format und `git diff --check`
bestanden. Keine Kamera, kein Serial-Port und kein Rerun-Viewer wurde geöffnet.

Der folgende menschliche Lauf erreicht 493 Durchläufe in 19,78 s, also
24,9 Hz. Die Arbeitszeit liegt meist bei 38..43 ms und damit über dem
33,3-ms-Budget für 30 Hz; die FPS-Wartepause entfällt fast vollständig.
Nach einem gRPC-Abbruch werden noch 29,7 Hz bei 29,3 ms Arbeit gemeldet.
Der Nutzer bestätigt ausdrücklich, das Rerun-Fenster selbst geschlossen zu
haben. Damit sind der Verbindungsabbruch und die Flush-Fehler beim Beenden
erklärt; dieser Lauf belegt keinen spontanen Viewer-Absturz.

Softwaremessung ohne Hardware oder Viewer: Rerun SDK 0.33.1, zwei synthetische
RGB-Bilder 640×480 mit Zufallsinhalt, jeweils 20 Messungen nach vier Warmups,
Rerun-Logging und Verbindung vollständig gemockt. Median für zwölf Skalare
0,49 ms; zwei JPEG-Bilder plus zwölf Skalare 13,66 ms; reine Vorbereitung
beider JPEG-Bilder 12,54 ms. Das weist CPU-Aufwand im synchronen Vorschaupfad
nach. Die Zahlen sind keine Messung des echten Kamerainhalts oder der
Transport-/Viewer-Kosten. Die Anzeigekosten am Arm sind noch über denselben
Aufruf mit aktiven Kameras und `--no-display-data --duration=10` abzugleichen.
Aus diesem Log werden keine weiteren Treiber- oder Timingänderungen abgeleitet.

## 17. Wrist-roll-Sprung und Greiferwert außerhalb der bisherigen Annahme

Der nächste menschliche Kalibrierlauf am 13.11.2026 um 16:11:08 erreicht
`wrist_roll`. Davor wurde für `wrist_flex` 664..3150 angezeigt. Für wrist_roll
stehen bereits 172..3960 im überwachten Bereich. Der konkrete Abbruch lautet
2798 -> 199, Differenz -2599 Ticks. Die vollständigen Messungen sind:

```text
vorher: [1968, 3254, 2622, 3012, 2798, 1192]
danach: [1968, 3254, 2622, 3012,  199, 1192]
```

Nur wrist_roll ändert sich zwischen diesen beiden Vektoren. Der große Sprung
begründet den vereinbarten konservativen Abbruch, beweist mit diesen beiden
Stützstellen aber keinen tatsächlichen Übergang direkt an 4095/0. Es wird weder
entwrappt noch die Schwelle erhöht. Für die bisherige Kalibrierung ist ein
zusammenhängender benutzter wrist_roll-Bereich ohne Encoderübergang erforderlich,
der den gewählten Referenznullpunkt enthält. Kein weiterer kompletter Versuch,
bevor die beiden folgenden Punkte getrennt geprüft sind.

**Neue offene Hardwarefrage:** Der Follower-Greifer meldet in beiden Paketen
1192. Das liegt drei Ticks unter der in AGENTS.md festgelegten Grenze 1195.
Die derzeitige Follower-Validierung würde eine gemessene Kalibrierung mit diesem
Minimum ebenfalls ablehnen; auch der erfasste Referenzpunkt muss im Bereich
liegen. Ist 1192 ein wiederholt erreichter mechanischer Endpunkt/Messabweichung,
und gilt die Herstellergrenze 1195..2833 ausschließlich für gesendete Ziele?
Vor einer Anpassung der Kalibrierungsregeln tatsächliche ruhende und manuell
erreichte Greiferwerte messen und mit dem Nutzer klären. Keine automatische
Erweiterung oder Begrenzung der Messdaten auf die bisherigen Konstanten.

Zur Messung erhält ausschließlich die bestehende menschliche Diagnose
`--reads=100 --read-interval=0.2`: mehr Positionsabfragen mit expliziter Pause
zwischen den Abfragen und abschließender Min/Max-Tabelle aller sechs Gelenke.
Das ergibt bei schnellen Antworten rund 20 Sekunden Beobachtungszeit. Default
bleibt drei Abfragen ohne zusätzliche Pause. Protokoll, Antworttimeout, Bridge-
und Torque-off-Befehle bleiben unverändert. Es werden weiterhin weder CMD 97
noch Torque-on gesendet. Die Min/Max-Werte werden nur angezeigt und weder als
Kalibrierung gespeichert noch gefiltert. Werte ohne Positionsantwort gehen nicht
in die Statistik ein; bekannte Firmware-Prüfsummentoleranz bleibt erhalten.

Für den nächsten menschlichen Test den Arm abstützen, wrist_roll ruhig halten
und nur den Greifer langsam ohne Kraft durch seinen benutzbaren Bereich bewegen:

```powershell
uv run --directory C:\Users\mario\robot\lerobot-nexarm --locked python scripts/diagnose_nexarm.py --port=COM13 --reads=100 --read-interval=0.2
```

Zur Auswertung genügt zunächst die abschließende Tabelle, insbesondere die
Zeile `gripper: min=..., max=...`. Ein wirklicher gemessener Greiferbereich und
die mechanische Richtung wurden bislang noch nicht abschließend bestätigt.

Softwareprüfung der Diagnoseergänzung: 103 Diagnose-/Kalibrierungstests
bestanden. Neue Mocks prüfen explizite Pausen zwischen Abfragen, unverändert
angezeigte Greiferwerte unter 1195, Min/Max bei fehlenden Antworten und ungültige
Argumente vor Portöffnung. Ruff und `git diff --check` bestanden; Motorbus-
SHA-256 weiterhin unverändert. Es wurde kein echter Hardwareaufruf ausgeführt.

### 100 Antworten, aber auffällige Randwerte im Min/Max-Ergebnis

Der Nutzer liefert das Ergebnis des längeren Diagnoseaufrufs: 100/100
Positionsabfragen beantwortet. Die Tabelle zeigt shoulder_pan 0..1963,
shoulder_lift 3255..4095, elbow_flex 2636..4095, wrist_flex 3034..4095,
wrist_roll 544..1411 und gripper 1191..4095. Ob außer dem Greifer andere Gelenke
bewegt oder durch fehlende Abstützung abgesenkt wurden, ist nicht bestätigt.
Diese Tabellenwerte dürfen noch nicht als kalibrierte mechanische Grenzen
übernommen werden; insbesondere ist gripper=4095 außerhalb der bisherigen
Herstellerannahme.

Die beiden tatsächlich mitgelieferten letzten RX-Frames enthalten dagegen nur
Werte innerhalb 0..4095: `[1963,3255,2636,3034,1411,1192]` bzw.
`[1963,3255,2636,3034,1410,1192]`. Beide vollständigen Prüfsummen wurden direkt
nachgerechnet und stimmen (0xAE bzw. 0xAF). Die auslösenden früheren 0-/4095-
Samples samt RX-Payload fehlen im Ausschnitt.

**Wichtiger Befund im unverändert übernommenen alten Treiber:**
`bus.py:read_positions()` decodiert sechs vorzeichenbehaftete 16-Bit-Werte und
begrenzt jeden anschließend auf 0..4095. Deshalb können negative Drahtwerte als
0 und Werte über 4095 als 4095 in der Tabelle erscheinen. Das ist kein neu
eingeführter Portierungsunterschied. Die vorherige Formulierung, Werte würden
im Diagnose-Min/Max nicht gefiltert, war insofern ungenau: Die Diagnose nimmt
keine weitere Begrenzung vor, erhält aber bereits vom Originaltreiber begrenzte
Werte. 100/100 ist daher ein Antwortzähler, keine numerische Qualitätsprüfung.

Nächster Schritt ohne erneuten Hardwarelauf: aus der vorhandenen Terminalausgabe
ein früheres `POSITIONS` mit 0 oder 4095 und den zugehörigen vollständigen
`RX buffer` anfordern. Daraus lässt sich unterscheiden, ob bereits der Drahtwert
ungültig war oder der Grenzwert selbst übertragen wurde. Keine Verbreiterung
der Greifergrenzen, kein Entwrappen und kein stilles Verwerfen von Messungen
allein aufgrund der zusammengefassten Min/Max-Werte.

Der Nutzer vermutet als Erklärung eine mechanisch mögliche volle oder mehrfache
Umdrehung. Für wrist_roll ist damit ein Encoderübergang plausibel, aber weder
das konkrete Gelenk noch ein Mehrturn-Datenformat sind anhand dieser Aussage
nachgewiesen. Ein Single-Turn-Übergang 4095 -> 0 verlässt den 12-Bit-Bereich
nicht; er überschreitet die Grenze seiner linearen Darstellung. Ob die Firmware
stattdessen vorzeichenbehaftete Mehrturn-Werte sendet, bleibt anhand eines
auffälligen RX-Frames zu prüfen. Diese Fälle nicht mit dem Clipping des alten
Treibers gleichsetzen.

Der freigegebene Kalibrierungsansatz unterstützt weiterhin ausschließlich einen
zusammenhängenden verwendeten Rohbereich ohne Encoderübergang, der die gewählte
Referenzpose einschließt. Beim Kalibrieren daher keine vollständigen Runden
erzwingen und vor der Encodergrenze umkehren. Die Greiferwerte 1191..4095 und
die Randwerte anderer Achsen sind durch eine mögliche wrist_roll-Umdrehung
noch nicht erklärt. Für echte Mehrturn-Unterstützung wären zunächst unveränderte
Drahtwerte und anschließend eine gesondert festgelegte Winkel-/Kalibrierungs-
darstellung nötig; der Wrap-Schutz wird nicht allein aufgrund der Vermutung
entfernt und die bisherigen Greifergrenzen werden nicht automatisch erweitert.

### Gespeicherter Ruhetest vollständig ausgewertet

Der Nutzer liefert einen neuen ruhenden Lauf; zusätzlich liegt dessen gesamte
Ausgabe in `.uv-cache/positions-check.log` vor. Die Datei wurde ohne Serial-
Zugriff direkt gelesen (UTF-16) und sämtliche 100 RX-Frames unabhängig als sechs
vorzeichenbehaftete Little-Endian-Werte **vor dem Treiber-Clipping** decodiert.
Alle 100 Frames haben exakt den CMD-96-Aufbau mit zwölf Payloadbytes und eine
korrekte vollständige Prüfsumme. Keine Timeouts, keine Werte außerhalb 0..4095.

Die aus den Drahtwerten berechneten Bereiche stimmen mit der Ausgabe überein:

| Gelenk | Min | Max |
| --- | ---: | ---: |
| shoulder_pan | 2076 | 2076 |
| shoulder_lift | 3300 | 3310 |
| elbow_flex | 1711 | 1711 |
| wrist_flex | 3078 | 3078 |
| wrist_roll | 1053 | 1054 |
| gripper | 2782 | 2784 |

Damit ist in diesem Ruhetest eine stabile Kommunikation ohne die zuvor
beobachteten Randwert-Ausreißer belegt. Eine Ursache ausschließlich bei Bewegung,
Mehrturn-Werte oder ein Fehler unter anderen Bedingungen sind dadurch noch nicht
nachgewiesen. Der Ruhetest misst keine mechanischen Endpunkte.

Als nächsten unterscheidenden menschlichen Test nur den Greifer langsam bewegen,
alle übrigen Gelenke abgestützt ruhig halten und denselben 100er-Lauf in
`.uv-cache/positions-gripper.log` speichern. Die getrennte Datei erhält die
Ruhemessung für einen direkten Vergleich. Der Agent wertet anschließend wieder
die vollständigen Drahtwerte aus; keine neue Kalibrierung und keine Änderung
der bisherigen Grenzwerte aus dem Ruhetest ableiten.

## 18. Ungültiges erstes Positionspaket mit gültiger Prüfsumme nachgewiesen

Die vollständige Datei `.uv-cache/positions-gripper.log` wurde nach dem
menschlichen Test direkt ausgewertet. Es gibt 100 CMD-96-Antworten mit korrekten
vollständigen Prüfsummen. Das **erste Paket** ist jedoch semantisch ungültig:

```text
ff ff ff 0e 60 01 00 ff ff cd 52 01 40 20 02 00 20 f1
vorzeichenbehaftet: [1, -1, 21197, 16385, 544, 8192]
alter Treiber:     [1,  0,  4095,  4095, 544, 4095]
```

Damit sind die zuvor verdächtigen 0-/4095-Anzeigen mindestens für diesen
konkreten Datensatz durch das Begrenzen ungültiger Drahtwerte erklärt. Das ist
kein Nachweis einer mechanischen 360-Grad-Bewegung. Warum das Gerät das Paket
mit gültiger Prüfsumme erzeugt, ist weiter offen; weder Firmwareursache noch
Verdrahtungsursache werden daraus behauptet. Eine bloße Prüfsummenprüfung reicht
hier nachweislich nicht aus.

Die übrigen 99 Antworten liegen innerhalb 0..4095. Der Greifer bleibt dort
2782..2784; damit wurde kein ausreichender Greiferweg gemessen. Der Nutzer sagt,
er habe nicht darauf geachtet, ob die Backen tatsächlich bewegt wurden. Es gibt
somit weiterhin keinen bestätigten vollständigen Greiferbereich.

Umgesetzte Korrektur vor weiteren Kalibrierungsversuchen:

- Den originalen `bus.py` samt dessen Firmware-Prüfsummentoleranz unverändert
  lassen. Ein eigener `ValidatedNexArmMotorsBus` prüft Positionsantworten vor
  dessen Begrenzung auf passenden CMD 96, genau zwölf Payloadbytes und sechs
  Werte innerhalb der festgelegten Hardwaredomäne 0..4095.
- Ungültige Antworten mit Inhalt und Warnung verwerfen und zählen. Dafür die
  bereits vorhandenen maximal drei Leseversuche und ihre Wartezeiten verwenden;
  keine unbegrenzten Wiederholungen, kein Ersatz durch zwischengespeicherte oder
  erfundene Positionen. Nach drei erfolglosen Versuchen bleibt es beim Fehler.
- Follower, Leader, Rohwert-Teleoperation und Diagnose an diese Prüfung anbinden.
  Dies ist eine offen dokumentierte Eingangsvalidierung aufgrund eines konkreten
  fehlerhaften Frames, keine Änderung von Frames, Torque-/Bridge-Befehlen,
  Baudrate oder gültigen Gelenkwerten.
- 0 und 4095 selbst bleiben erlaubt. Werte wie gripper=1191/1192 werden nicht
  verworfen, weil sie innerhalb der 12-Bit-Domäne liegen. Die separate Frage der
  Greifer-Kalibriergrenzen bleibt unverändert offen; echte Wrap-Sprünge zwischen
  gültigen Werten bleiben vom Kalibrierungswächter erfasst.
- Den exakten geloggten Frame als Regression verwenden, einschließlich der
  folgenden gültigen Antwort, dauernd ungültiger Antworten, Grenzwerten und der
  bekannten kurzen Leader-Prüfsumme. Echte Serial-Ports bleiben in Tests gesperrt.

Die Prüfung liegt in `validated_bus.py` vor der alten Begrenzung in `_send`.
Follower und Leader sowie die beiden menschlichen Rohwert-/Diagnoseskripte
verwenden diesen abgeleiteten Bus. Die Diagnose gibt zusätzlich
`Rejected invalid position replies: N` aus. Jeder ungültige Datensatz erzeugt
eine Warnung mit Original-Payload; er wird nicht still entfernt. Dauerhaft
ungültige Antworten enden nach den vorhandenen drei Versuchen im Lesefehler.

Softwareprüfung: vollständige aktuelle Suite **205 bestanden**. Der exakte
geloggte fehlerhafte Frame wird vor dem Begrenzen verworfen, die nachfolgende
gültige Antwort unverändert zurückgegeben und eine einzelne Zurückweisung
gezählt. Weitere Regressionen decken drei ungültige Antworten, falschen CMD,
falsche Länge, erlaubte Randwerte und kurze Leader-Prüfsummen ab. Die Diagnose-
Statistik enthält das verworfene Paket nicht mehr. Ruff und `git diff --check`
bestanden. `bus.py` bleibt SHA-256
`d53a53ba1f61fa9584b203e25c30227a184a4de011b64d2ad4e0441b1c155b40`.

Diese Korrektur beseitigt die nachgewiesene Übernahme dieses ungültigen Pakets,
nicht die unbekannte Ursache im Gerät. Sie bestätigt noch keinen vollständigen
Greiferweg und keine fertige Kalibrierung. Der Nutzer hat die sichtbare Bewegung
der Backen im Messlauf nicht beobachtet; eine gezielte Greifermessung mit
beobachteter Öffnung/Schließung bleibt der nächste menschliche Schritt.

## 19. Cloud bridge

Die am 13.11.2026 korrigierte `../CLOUD_BRIDGE.md` erweitert den bisherigen
Auftrag ausdrücklich um eine synchrone F3A-Cloud-Brücke. Alle neuen Module
kommen nach `scripts/cloud/`; das separate inference-Grundgerüst und vastai
bleiben Referenzen. Keine echten Vast-Instanzen starten/stoppen/löschen, keine
echten SSH-Verbindungen und keine Hardwaretests durch den Agenten. Die
Protokoll-, Kalibrierungs- und Normierungsregeln des Plugins bleiben bestehen.

Plan vor Implementierung:

1. Gemeinsame, begrenzte JSON-Schemas und JPEG-Konvertierung; HTTP-Server nur
   auf 127.0.0.1:8000 mit `/health`, `/predict`, Lade-/Warmupstatus und GPU-Lock.
   Mockmodus ohne Modell-/CUDA-Import. GPU-Imports ausschließlich im Real-Backend.
2. F3A mit lokalen SO-101-/Encoderpfaden laden, optional lokaler PEFT-Adapter und
   Text-Encoder-Offload; Policy und gekoppelte Prozessoren je Anfrage zurücksetzen,
   vollständigen Chunk vorhersagen, postprocessen und 32 absolute Aktionen liefern.
3. Laptop-Client mit bestehendem normiertem Follower, explizit scene/wrist,
   standardmäßig dry-run, 5-s-Timeout, Sprungprüfung gegen frisch gemessenen
   Zustand, 30-Hz-Ausführung, letzter tatsächlich gesendeter Aktion als Anker,
   Laufzeitlimit, JSONL und optionaler Aufzeichnung ausgeführter Aktionen.
   Fehlende Kalibrierung vor dem Connect melden; kein Rohwert-Bypass für F3A.
4. Vast-Sitzungsskripte mit expliziter .env, SDK, direktem SSH-Endpunkt oder Proxy,
   tmux, Hintergrundtunnel und Health-Polling; saubere Stop-/Destroy-Trennung.
   Nur die menschlich ausgeführten Skripte dürfen reale Cloud-Aktionen auslösen.
5. Schema-, Bild-, API-/Client- und Sitzungstests mit Mock-Modell, Fake-Follower,
   Fake-SDK und Fake-SSH; zusätzlich separater realer GPU-Äquivalenztest für Chunk
   versus 32 sequenzielle select_action-Aufrufe. Doku und Beispiele fertigstellen.

Verifizierte Semantik am unveränderten LeRobot-Pin
`2f05d8f64d62a865c368a9fdf0ba3d8423e28035`:

- `ActionHistoryUnnormalizerProcessorStep.action()` unterstützt `(B,T,6)`.
  Die fünf Delta-Kanäle werden per `cumsum(1) + output_anchor` integriert; der
  Greiferkanal `-1` bleibt absolut. Kein eigener Integrator in unserer Brücke.
- `ObservationHistoryNormalizerProcessorStep` setzt `output_anchor` auf die
  letzte vorausgehende absolute Aktion aus `observation.command_history`.
  Im Offlinepfad verlangt es genau `(B,n_obs_steps,6)`, passende Zustände und
  Bilder. Der Online-Bootstrap wiederholt bei Episodenbeginn den ersten Zustand.
- Die kleine config.json von SO-101-Revision
  `c9e13b2aca6a0a472b3ea03fd90cff32d3e85849` wurde über den bestehenden HF-Zugang
  ohne Gewichte nach `.uv-cache/f3a-contract-c9` geladen und geprüft:
  **n_obs_steps=8**, chunk_size=42, n_action_steps=32, fps=30, conditioning=history,
  condition_on_past_actions=true, action_representation=delta, absolute_dims=[-1],
  Kameras scene/wrist. Auch die ältere lokale e258-Revision erwartet acht Schritte.
- Deshalb reicht die in der MD skizzierte einzelne Beobachtung mit einem
  Vorgängerbefehl für diesen konkreten Checkpoint nicht. Rückwärtskompatible
  Erweiterung um optionale vollständige `history`: der Client sendet acht
  Bild-/Zustands-/Vorgängerbefehl-Sätze, gesammelt während der Steuerung.
  Nur beim Episodenstart darf der erste Satz wie im Upstream-Bootstrap wiederholt
  werden. Folgeanfragen ohne erforderliche Historie scheitern verständlich;
  keine still wiederholten Einzelbilder als vorgetäuschte Bewegungshistorie.
- Für den GPU-Vergleich muss die sequenzielle Seite den Postprocessor nach jeder
  Aktion aktualisieren. Ein erneutes Einspeisen desselben expliziten Ankers pro
  Einzelschritt wäre kein äquivalenter Test, weil es die Integration zurücksetzt.

Die weiterhin fehlende vollständige Kalibrierung samt Referenzpose, Richtungen
und Greiferbereich blockiert später echte Modellbewegungen, nicht die Erstellung
und Offline-Prüfung der API. Der GPU-Rauch-/Äquivalenztest bleibt menschliche
Abnahme; die lokale Entwicklungsmaschine lädt keine F3A-Gewichte.

## 20. Cloud-Inferenz liegt jetzt in `cloud/` (13.11.2026)

Auf Wunsch des Nutzers ersetzt eine schlanke Fassung im Plugin-Repo das separate
`../inference`-Projekt: `cloud/deploy.py` (Laptop), `cloud/setup_remote.sh` und
`cloud/server.py` (Instanz). Das weicht vom Ablageort `scripts/cloud/` aus
`../CLOUD_BRIDGE.md` ab; `../inference` bleibt unverändert liegen und kann gelöscht werden.

- `deploy.py up` mietet automatisch die günstigste RTX 5090 (Preisgrenze `--max-price`,
  Standard 1 $/h), richtet sie ein und hält den SSH-Tunnel offen. Das eigene Gerät wird
  am Label `nexarm-f3a` erkannt; es gibt keine lokale Zustandsdatei mehr.
- `setup_remote.sh` folgt der BFL-Anleitung „SO-101 with LeRobot“ (Torch 2.11 cu128,
  `.[training,flux3,peft,diffusion]`, NATTEN, `hf download` beider Pakete an den dort
  genannten Revisionen), aber am Projekt-Pin statt auf `main`.
- `server.py` lädt Policy und gespeicherte Prozessoren wie in `docs/source/flux3.mdx`,
  setzt sie je Anfrage zurück und ruft `predict_action_chunk` auf. Anfrage: `task` und
  1 bis 8 `frames`; fehlende Historie wird durch Wiederholen des ältesten Frames ergänzt.
- Bewusst gestrichen gegenüber `../inference`: Jobjournal und Prozesssperre,
  Abgleich unklarer Mietantworten, reproduzierbares Quellarchiv, GPU-Lockfile,
  Chunk-gegen-sequenziell-Vergleich, Mietpläne, Revisionsprüfung in `/health`,
  strenge Wertebereichsprüfung der Anfrage, automatisches Stoppen bei Fehlern.
  Nach einem Fehler läuft die Instanz weiter; das Skript sagt das und nennt `down`.
- Geprüft ohne GPU und ohne Cloud: Angebotswahl, SSH-Endpunkt, Bilddekodierung,
  Historie und Mock-Server (`tests/test_cloud.py`). **Nicht geprüft:** echte Miete,
  Installation auf der Instanz und der Lauf mit dem echten Modell. Der Client am Arm
  (`client.py` aus `CLOUD_BRIDGE.md`) existiert noch nicht.

## 21. Versehentliche Zusammenführung zurückgenommen (13.11.2026)

Ein zweiter Agent hatte zwischenzeitlich das komplette `../inference`-Paket nach
`cloud/` kopiert und die schlanken Einstiege zu Weiterleitungen gemacht. Das war
nicht beabsichtigt. Auf Anweisung des Nutzers gilt wieder Abschnitt 20: `cloud/`
enthält nur `deploy.py`, `setup_remote.sh`, `server.py`, README und `.env.example`.
Die große Fassung liegt weiterhin committet in `../inference`.

## 22. Cloud-Client `cloud/client.py` (14.11.2026)

Plan und Umsetzung des Laptop-Clients nach `../CLOUD_BRIDGE.md`, angepasst an die
acht Beobachtungsschritte des Checkpoints.

- Schleife: beobachten, Plan holen, ersten Befehl prüfen, 32 Befehle mit 30 Hz senden
  und dabei jeden Takt in einen Ringpuffer mit acht Plätzen legen. Der nächste Plan
  bekommt diese acht Takte. Am Pin sind die Beobachtungsindizes
  `range(1 - n_obs_steps, 1)`, also aufeinanderfolgende 30-Hz-Takte;
  `history_snapshots=2` betrifft nur die interne Videokodierung.
- `last_command` eines Takts ist der vom Plugin zurückgegebene, tatsächlich gesendete
  Befehl. Im Dry-run bleibt er leer: Es wurde nichts gesendet, also behauptet der
  Client auch keine Befehlshistorie. Das weicht vom ersten Planentwurf ab.
- Sicherheit: Dry-run als Standard, Sprungprüfung (15° / Greifer 30), Server-Timeout 5 s,
  Laufzeitgrenze, Strg+C über das normale `disconnect()`. Keine zweite Begrenzung
  neben dem Plugin. Vor dem Verbinden wird die Follower-Kalibrierung geprüft, damit
  kein Kalibrierdialog startet.
- `--fake-robot` ersetzt Arm und Kameras durch feste Werte und prüft so Server und
  Tunnel ohne Hardware.
- Kameraname: `teleoperate.yaml`, `record.yaml` und `inference.yaml` verwenden jetzt
  `scene` statt `front` (Entscheidung aus 11.7); die `rename_map` im Inferenzbeispiel
  entfällt. Das weicht vom Default `front` in `../AGENTS.md` ab.
- Nicht umgesetzt: Aufzeichnung als LeRobot-Dataset (`--record`).
- Geprüft: Tests mit Fake-Follower (Dry-run, Historie, Sprungprüfung, Timeout, Strg+C,
  30-Hz-Takt, Laden der Beispiel-YAML) und ein Lauf über echtes HTTP gegen den lokalen
  Mock-Server. **Nicht geprüft:** echter Arm, echte Kameras, echtes Modell.