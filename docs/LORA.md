# LoRA-Training von FLUX 3 Action auf NexArm-Daten: Vorbereitung

Stand: 14.11.2026. Grundlage sind BFLs Anleitung „SO-101 with LeRobot", die LeRobot-Doku
`flux3.mdx` am gepinnten Commit und der Code in `lerobot/policies/flux3`. Trainiert wurde
noch nichts.

## Ergebnis

Ein Training mit den vorhandenen 29 Episoden ist technisch direkt möglich. Die Daten
erfüllen das geforderte Format, und mit der festen Statistik des Checkpoints wird kein
einziger Wert abgeschnitten. Zwei Dinge sprechen gegen ein gutes Ergebnis: Die Datenmenge
ist klein (9,3 Minuten; BFL nennt etwa 200 Demonstrationen für sein Beispiel), und zwei
Gelenke liegen weit außerhalb des Bereichs, den der Checkpoint kennt.

## Was die Anleitung verlangt und was wir haben

| Anforderung | Unsere Aufnahmen |
| --- | --- |
| LeRobot-Dataset v3, 30 Hz | erfüllt |
| Sechs absolute Befehle, sechs gemessene Werte, Gelenkreihenfolge wie SO-101 | erfüllt |
| Armgelenke in Grad, Greifer in Prozentpunkten | erfüllt |
| Aufgabentext pro Episode | erfüllt („put the small box on top of the big box") |
| Kameras `observation.images.scene` und `observation.images.wrist` | erfüllt, keine `rename_map` nötig |
| Durchgehend dieselbe Kalibrierung, auch später bei der Inferenz | erfüllt für die Aufnahmen; die Datei liegt bei den Aufnahmen, nicht im Repo |
| Ein Dataset | offen: es sind vier einzelne (3 + 3 + 3 + 20 Episoden) |

## Die Statistik des Checkpoints bleibt fest

Die Anleitung ist eindeutig: Die Normalisierung gehört zum Checkpoint und wird beim
LoRA-Training nicht ersetzt. Andere Statistiken würden eine eigens vorbereitete Basis
brauchen. Der Code rechnet jeden Wert so um und schneidet bei ±6 ab:

    normalisiert = 2 × (Wert − q01) / (q99 − q01) − 1

BFLs eigene Daten liegen damit etwa zwischen −1 und 1. Unsere 29 Episoden ergeben:

| Größe | 1. Perzentil | Median | 99. Perzentil |
| --- | --- | --- | --- |
| Zustand `shoulder_pan` | −0,04 | 0,21 | 0,47 |
| Zustand `shoulder_lift` | −3,67 | −3,14 | −2,31 |
| Zustand `elbow_flex` | −2,85 | −2,26 | −1,09 |
| Zustand `wrist_flex` | −0,82 | 0,00 | 1,21 |
| Zustand `wrist_roll` | 0,13 | 0,33 | 0,51 |
| Zustand Greifer | −1,01 | −0,99 | 2,63 |
| Befehlsschritte der fünf Armgelenke | −0,92 | um 0 | 0,52 |
| Befehl Greifer (absolut) | −1,00 | −0,99 | 2,69 |

- Abgeschnitten wird nichts; alle Werte bleiben unter 6.
- Die Befehlsschritte pro Takt passen gut. Das Modell sagt Schritte vorher, keine absoluten
  Winkel; das ist der Teil, der zählt.
- `shoulder_lift` und `elbow_flex` liegen als Zustand komplett außerhalb, der geschlossene
  Greifer ebenfalls. Das Modell bekommt diese Eingaben in einem Bereich, den es nie gesehen
  hat. Laut Anleitung werden die Köpfe für Zustand und Aktion beim LoRA voll trainiert und
  können das lernen; ob 29 Episoden dafür reichen, ist offen.

## Offene Entscheidungen

1. **Versatz für `shoulder_lift` und `elbow_flex`?** Addiert man 156° und 133°, liegen
   beide mitten im Bereich des Checkpoints. Die Befehlsschritte ändern sich dadurch nicht.
   Dagegen spricht: Wir wissen nicht, welche Pose bei BFLs Arm welchem Winkel entspricht.
   Ein Versatz macht die Zahlen vertraut, aber womöglich mit falscher Bedeutung, und er
   wäre eine zusätzliche Umrechnung, die bei Training und Inferenz gleich sein muss.
   Empfehlung: zuerst ohne Versatz trainieren, den Versatz nur als zweiten Versuch.
2. **Greiferrichtung.** In unseren Daten ist 0 offen und 100 geschlossen. Der Checkpoint
   hat 0,5 bis 54 gesehen; welche Richtung er meint, steht nirgends. Beim SO-101 in LeRobot
   ist üblicherweise 100 offen. Für das Training ist das unkritisch, solange Aufnahmen und
   Inferenz dieselbe Kalibrierung benutzen.
3. **Mehr Daten.** Mehr Episoden derselben Aufgabe mit unveränderter Kalibrierung und
   Kameraposition sind der sicherste Hebel.

## Vor dem Training zu erledigen

- Die vier Datasets zu einem zusammenführen. `lerobot-edit-dataset` ist installiert; die
  genaue Syntax ist noch nicht geprüft.
- Episode 16 des 20er-Satzes entfernen oder die Frames 156/157 herausnehmen (Lesefehler,
  alle Gelenke springen in einem Takt).
- Die neun Episoden der drei kleinen Sätze ansehen. Sie enden nach knapp 20 s, vermutlich
  am Zeitlimit, und sind womöglich nicht zu Ende geführt.
- Die Kalibrierdateien ins Repo oder an einen festen Ort legen. Sie gehören ab jetzt zum
  Modell.
- Beachten: Die Voreinstellung hält die letzten 20 % der Episoden zur Auswertung zurück.
  Bei 28 Episoden bleiben etwa 22 zum Training.

## Training

Auf der gemieteten Instanz liegen LeRobot, Modell und Encoder schon so, wie die Anleitung
es verlangt (`/workspace/lerobot`, `models/flux-3-action-so101`, `models/flux-3-action-base`).
Der Aufruf nach Anleitung, für ein lokales Dataset ergänzt um `--dataset.root`:

```sh
cd /workspace/lerobot && source .venv/bin/activate
python -m lerobot.scripts.lerobot_train \
  --config_path=examples/flux3/lora.json \
  --policy.path=models/flux-3-action-so101 --policy.device=cuda \
  --policy.video_vae_id=models/flux-3-action-base/video_vae.safetensors \
  --policy.text_encoder_id=models/flux-3-action-base/text_encoder \
  --dataset.repo_id=local/nexarm_f3a_stack_boxes --dataset.root=/workspace/data/nexarm_f3a_stack_boxes \
  --output_dir=outputs/nexarm_lora
```

Die Voreinstellung: eine GPU, Batch 2, Akkumulation 4, 10 000 Mikroschritte (2 500
Optimiererschritte), Rang 32, BF16, Gradient Checkpointing, EMA 0,999. Gespeichert wird
alle 500 Mikroschritte.

Nicht bekannt:

- ob das Training in die 32 GB einer RTX 5090 passt; die Anleitung sagt nur, man solle den
  Speicherbedarf auf der eigenen Hardware prüfen,
- wie lange 10 000 Mikroschritte dauern und was sie kosten,
- ob `--dataset.root` mit dem zusammengeführten Dataset so funktioniert.

Ein kurzer Probelauf mit `--steps=40` klärt die ersten beiden Punkte billig.

## Danach: Inferenz

`lerobot-rollout` aus der Anleitung braucht Modell und Arm am selben Rechner und passt
nicht zu unserem Aufbau. Unser `cloud/server.py` hat dafür `--adapter`: Er lädt den
Basis-Checkpoint und darauf den trainierten Adapter. Der Client bleibt unverändert.

Reihenfolge für den ersten Test:

1. Client mit `--sim` gegen das trainierte Modell. Die Simulation benutzt dieselben
   Einheiten wie die Aufnahmen.
2. Client mit echtem Arm im Dry-run.
3. `--execute`.

Die Anleitung empfiehlt, den normalen und den EMA-Adapter mit denselben Starts zu
vergleichen; EMA ist beim SO-101 nicht automatisch besser.
