# Stand des Projekts

Stand: 14.11.2026. Diese Datei beschreibt, was gebaut wurde, was dabei herauskam und was
offen ist. Details zu einzelnen Entscheidungen stehen in `PORTING_NOTES.md`, die Bedienung
der Cloud in `cloud/README.md`.

## Kurzfassung

- Die Cloud-Strecke läuft mit dem echten Modell: Ein Befehl mietet eine RTX 5090, lädt
  FLUX 3 Action und stellt die API bereit. Der Client hat dagegen mit einem simulierten Arm
  Pläne geholt und mit 30 Hz ausgeführt.
- Am echten Arm ist bisher nur die rohe Teleoperation gelaufen. Der Client war noch nie mit
  dem Arm verbunden.
- Der Engpass ist die Kalibrierung des Followers. Ohne sie startet der Client mit Arm nicht,
  und die Einheiten für das Modell stimmen nicht.

## Was gebaut wurde

| Teil | Ort | Aufgabe |
| --- | --- | --- |
| Plugin | `src/lerobot_robot_nexarm/` | Serielles Protokoll, Follower und Leader für LeRobot, Kalibrierung, Umrechnung Ticks ↔ Grad |
| Rohe Teleoperation | `scripts/teleoperate_raw.py` | Leader führt Follower ohne Kalibrierung, mit Kameravorschau |
| Bereitstellung | `cloud/deploy.py` | `up`, `status`, `down`: mieten, einrichten, Tunnel öffnen, stoppen |
| Einrichtung | `cloud/setup_remote.sh` | Installation auf der Instanz nach der BFL-Anleitung, Modell-Download, Serverstart |
| Server | `cloud/server.py` | FastAPI mit `/health` und `/predict`, läuft auf der Instanz |
| Client | `cloud/client.py` | Schleife auf dem Laptop: beobachten, Plan holen, prüfen, 32 Befehle senden |

LeRobot ist auf Commit `2f05d8f64d62a865c368a9fdf0ba3d8423e28035` gepinnt, auf dem Laptop
und auf der Instanz.

## Wie die Cloud-Inferenz arbeitet

1. `deploy.py up` sucht die günstigste verifizierte RTX 5090, mietet sie und erkennt sie
   später am Label `nexarm-f3a` wieder.
2. `setup_remote.sh` installiert LeRobot mit Torch 2.11 (cu128) und NATTEN und lädt
   `flux-3-action-so101` und die nötigen Teile von `flux-3-action-base` an festen Revisionen.
3. Der Server lauscht nur auf `127.0.0.1:8000` der Instanz. Der Laptop erreicht ihn über
   einen SSH-Tunnel.
4. Der Client schickt die letzten bis zu acht Takte (zwei JPEGs, Gelenkwerte, letzter
   Befehl) und den Aufgabentext. Der Server antwortet mit 32 absoluten Befehlen.
5. Der Client prüft den ersten Befehl gegen den gemessenen Zustand (15°, Greifer 30) und
   sendet die 32 Befehle mit 30 Hz. Ohne `--execute` sendet er nichts.

## Ergebnisse

### Erster echter Lauf auf vast.ai (14.11.2026)

- Gemietet: RTX 5090 in Rumänien für 0,553 $/h.
- Die Installation lief durch: Torch 2.11.0+cu128 erkennt die Karte, LeRobot 0.7.1, NATTEN
  0.21.6. Der Modell-Download dauerte etwa dreieinhalb Minuten.
- Die Konfiguration des Checkpoints passt zu Server und Client: Kameras
  `observation.images.scene` und `observation.images.wrist`, `n_obs_steps` 8,
  `n_action_steps` 32, `chunk_size` 42, 30 fps.
- Zwei Fehler in den Skripten traten auf und sind behoben (Commit `9b1fe20`):
  - Ein abgebrochener Clone ließ einen halben `lerobot`-Ordner zurück, der nächste Lauf
    scheiterte mit `reference is not a tree`. Das Skript holt jetzt nur den gepinnten
    Commit und repariert einen solchen Ordner.
  - vast.ai meldet eine gestoppte Instanz als `exited`. `up` hat das als Fehler gewertet;
    jetzt startet es sie wieder. Diese Korrektur ist noch nicht gegen vast.ai geprüft.

### Client gegen das echte Modell, mit simuliertem Arm

Lauf über 25 Sekunden mit `--fake-robot --execute`, 9 Pläne:

| Messwert | Ergebnis |
| --- | --- |
| Rechenzeit des Modells pro Plan | 1,04 s |
| Übertragung und Tunnel | ca. 0,6 s |
| Latenz am Laptop pro Plan | 1,66 s (erster Plan 2,80 s) |
| Ausführungsrate der Befehle | 29,8 bis 29,9 Hz |

- Der Arm würde 1,07 s fahren und dann 1,66 s stehen. Die Bewegung wäre also ruckweise.
- Die geplanten Befehle selbst sagen nichts aus. Der simulierte Arm liefert graue Bilder
  und Nullstellung, und das Modell fuhr damit `shoulder_lift` innerhalb eines Plans um gut
  60°.
- Die Sprungprüfung sieht nur den ersten Befehl eines Plans. Eine große Bewegung innerhalb
  eines Plans fängt sie nicht ab.

### Tests ohne Hardware

- Mit FastAPI: 219 bestanden (`uv run --with fastapi --with httpx pytest`), Stand Commit
  `d7e53aa`. In der reinen Plugin-Umgebung 216 bestanden, 3 übersprungen.
- Der Client lief auch über echtes HTTP gegen den lokalen Mock-Server mit knapp 30 Hz.

### Aufnahme des Kollegen (13.11.2026)

Ordner `C:\Users\mario\robot\lerobot-20261113T055149Z-1-001`, aufgenommen am Arm mit dem
Hiwonder-Fork, nicht mit diesem Plugin.

- Ein Dataset im Format v3.0: 1 Episode, 599 Frames, 20 s, Aufgabe „put the small box on
  top of the big box", Kameras `scene` und `wrist` mit 640×480.
- Die Gelenkwerte sind rohe Ticks und keine Grad. Für das Modell sind sie so nicht
  verwendbar, lassen sich aber mit einer echten Kalibrierung nachträglich umrechnen.
- Die beiden Kalibrierdateien sind Platzhalter des Forks (0 bis 4095, Nullpunkt 2048).
- Rund 19 % der Kamerabilder sind Wiederholungen. Die Kameras liefern etwa 25 Bilder pro
  Sekunde.
- Leader-Arm und Bediener sind im Bild der Szenenkamera.
- Der Follower erreicht den Leader nicht überall: `shoulder_lift` in Ruhelage 3290 statt
  3445, Greifer offen 2776 statt 2833. Er folgt mit etwa 3 Takten Verzögerung.
- Der Greifer geht in dieser Episode nicht unter 1238.

### Weitere Aufnahmen (13.11.2026, nachmittags)

Ordner `C:\Users\mario\robot\lerobot-20261114T070646Z-1-001`: vier Datasets mit zusammen
29 Episoden derselben Aufgabe, davon ein Satz mit 20 Episoden (381 s).

- Die Gelenkwerte sind jetzt Grad und Greifer 0 bis 100, exakt nach der Formel des Plugins.
- Leader und Bediener sind nicht mehr im Bild.
- Die Kalibrierdatei, mit der aufgenommen wurde, liegt nicht im Ordner. Nullpunkte und
  Vorzeichen der Aufnahmen sind deshalb unbekannt.
- Der Greifer ist exakt auf 1195 bis 2833 abgebildet, vermutlich von Hand eingetragen.
- Episode 16 des 20er-Satzes enthält bei Frame 156/157 einen Lesefehler: Alle Gelenke
  springen in einem Takt.
- 22 bis 31 % der Kamerabilder sind Wiederholungen.

### Simulierter Arm in MuJoCo (14.11.2026)

`cloud/sim.py` ersetzt den Arm im Client durch ein MuJoCo-Modell (`--sim`). Das Modell
stammt aus `github.com/khanhthanhdev/lerobot-nexarm` und liegt uneingecheckt in
`third_party/`.

- Gegen den lokalen Mock-Server gelaufen: Der Client bekommt gerenderte Bilder, der Arm
  hält seine Stellung, ein Video wird geschrieben. Etwa 18 Takte pro Sekunde in Echtzeit.
- Gegen das echte Modell gelaufen: Der Arm fuhr nicht zu den Boxen, sondern hob
  `shoulder_lift` Plan für Plan an, bis die Sprungprüfung in Plan 4 abbrach.
- Ursache ist sehr wahrscheinlich die Nullstellung. Die Statistik im Checkpoint
  (`dataset_statistics.json`) zeigt, in welchem Bereich das Modell trainiert wurde
  (1. bis 99. Perzentil, in Grad):

  | Gelenk | von | bis |
  | --- | --- | --- |
  | `shoulder_pan` | −92 | 54 |
  | `shoulder_lift` | 85 | 184 |
  | `elbow_flex` | 61 | 179 |
  | `wrist_flex` | −24 | 81 |
  | `wrist_roll` | −125 | 60 |
  | `gripper` | 0,5 | 54 |

  Die Simulation startete mit `shoulder_lift` −1° und `elbow_flex` 18°, also weit außerhalb.
  Auch die Aufnahmen vom 13.11. liegen außerhalb (`shoulder_lift` −49 bis 28°).
- Zweiter Versuch mit verschobener Nullstellung (`shoulder_lift` und `elbow_flex` 90° in
  der CAD-Grundstellung, Greifer bis 54, Start mitten im Trainingsbereich): Der Arm
  streckte sich in vier Plänen flach nach vorn auf den Tisch und fuhr nicht zu den Boxen.
  Die Verschiebung ist geraten; welche Pose bei BFL welchem Winkel entspricht, ist
  unbekannt. Weiteres Raten an Vorzeichen bringt wenig.
- Die LeRobot-Doku sagt dazu, dass diese Werte zur Kalibrierung von BFLs eigenem Arm
  gehören und keine allgemeine SO-101-Kalibrierung sind. Vorgesehen ist ein LoRA-Training
  auf eigenen Daten mit durchgehend gleicher Kalibrierung.
- Annahmen: 0° ist die CAD-Grundstellung, Greifer 100 ist offen.
- Das fremde Repo nennt für den Follower-Greifer 1195 als offen und 2833 als geschlossen.
  Stimmt das, braucht der echte Greifer `drive_mode` 1, damit 100 wie beim SO-101 offen
  bedeutet. Das ist am Arm zu prüfen.

## Was am echten Arm gelaufen ist

- Rohe Teleoperation mit Follower an COM13 und Leader an COM14.
- Aufnahme mit zwei Kameras, allerdings mit dem Hiwonder-Fork.

Nicht gelaufen: Kalibrierung mit dem Plugin, `lerobot-teleoperate` und `lerobot-record` mit
dem Plugin, der Cloud-Client in Dry-run oder mit `--execute`.

## Offene Punkte

- **Kalibrierung des Followers.** Der Greifer misst 1191/1192, erlaubt ist ab 1195.
  `wrist_roll` springt über die Encodergrenze. Nullpunkte und Vorzeichen pro Gelenk muss
  jemand am Arm einstellen.
- **Schleifenrate mit Kameras.** In der rohen Teleoperation brauchte ein Takt 38 bis 43 ms,
  das wären weniger als 30 Hz.
- **Latenz.** 1,66 s pro Plan führen zu ruckweiser Bewegung. Eine nähere Instanz oder
  kleinere Anfragen könnten den Übertragungsanteil senken; das Modell selbst braucht 1,04 s.
- **Modell auf echten Bildern.** Ob der SO-101-Checkpoint am NexArm ohne Fine-Tuning etwas
  Sinnvolles plant, ist ungetestet.
- **Bridge-Modus.** Die Frage, was die Firmware beim Verlassen des Bridge-Modus tut, ist in
  `PORTING_NOTES.md` offen.
- **Nicht gebaut:** Aufzeichnung als Dataset im Client (`--record`), Umrechnung der
  Fork-Aufnahmen von Ticks in Grad.

## Abweichungen von `CLOUD_BRIDGE.md`

Die ursprüngliche Planung im Workspace-Ordner ist an diesen Stellen überholt:

- Der Code liegt in `cloud/`, nicht in `scripts/cloud/`.
- Statt `session_start.py`, `session_stop.py` und `status.py` gibt es ein `deploy.py`, das
  die Instanz auch selbst mietet. Es braucht keine `VAST_INSTANCE_ID`.
- `/predict` nimmt eine Liste von bis zu acht Takten (`frames`) statt eines einzelnen
  Bildpaars, weil der Checkpoint acht Takte Historie erwartet.
- Die Antwort enthält nur `commands` und `seconds`, keine `request_id` und keine
  aufgeschlüsselten Zeiten.
- Der Server macht keinen Warmlauf. Der erste Plan dauert deshalb länger.
- Im Dry-run bleibt `last_command` leer, damit keine Befehle als gesendet gelten, die der
  Arm nie bekommen hat.
- Die feste Kamera heißt in den Beispielen `scene` statt `front`.

## Nächste Schritte

1. Am Arm: Follower kalibrieren und die beiden Blocker (Greiferlimit, `wrist_roll`) klären.
2. Client im Dry-run mit Arm und Kameras gegen das echte Modell laufen lassen und die
   geplanten Befehle ansehen.
3. Erst danach `--execute`, mit gesetzten Koordinatenlimits, freiem Arbeitsbereich und
   einer Person am Netzschalter.
4. Ohne Arm möglich: die Aufnahmen durch das Modell schicken und die Pläne mit den
   Befehlen des Menschen vergleichen, sobald die 20 Runs da sind.
5. Ohne Arm möglich: den Client mit `--sim` gegen das echte Modell laufen lassen und das
   Video ansehen. Das prüft die Schleife und grob die Richtungen, aber nicht, ob das
   Modell die Aufgabe löst.

## Kosten im Blick behalten

`Strg+C` schließt nur den Tunnel. Die Instanz kostet weiter, bis `uv run cloud/deploy.py
down` gelaufen ist. `down --destroy` löscht sie samt Modell.
