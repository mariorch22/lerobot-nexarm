# F3A-SO-101-Vertragsprüfung

`contract_report.json` enthält Revision, SHA-256, Dateigrößen und gelesene Quantile.
Es wurde ausschließlich der kleine Vertrag des Checkpoints heruntergeladen,
kein `model.safetensors`, kein Encoder und keine anderen Modellgewichte.
Die heruntergeladenen Originale unter `flux3-so101/` sind lokal und gitignored.

Reproduktion mit einem freigeschalteten, per `hf auth login` angemeldeten Account:

```powershell
$files = @(
  "config.json",
  "dataset_statistics.json",
  "policy_preprocessor.json",
  "policy_postprocessor.json",
  "policy_preprocessor_step_3_flux3_observation_history_normalizer.safetensors",
  "policy_preprocessor_step_4_flux3_action_target_normalizer.safetensors",
  "policy_postprocessor_step_0_flux3_action_history_unnormalizer.safetensors"
)
hf download black-forest-labs/flux-3-action-so101 @files --revision e2584b2698e3b88368854976e354af87ec9893c6 --local-dir reference/flux3-so101
uv run python -B scripts/inspect_checkpoint_contract.py reference/flux3-so101 --report reference/contract_report.json
```

Das Skript liest nur lokale JSONs und kleine Normalizer-Dateien. Es prüft die
gleiche Revision aller Downloads und exakte Übereinstimmung der Quantile zwischen
JSON und allen drei Safetensors. Es initialisiert keine Policy und keine Hardware.

Die numerischen Quantile allein entscheiden die Einheit hier nicht: Alle
Zustandsquantile liegen innerhalb ±100. Die explizite Angabe `use_degrees=True`
in der [Modellkarte](https://huggingface.co/black-forest-labs/flux-3-action-so101#calibration-and-normalization)
legt Grad fest. Aktionsquantile beschreiben Deltas der ersten fünf Kanäle und
einen absoluten Greifer, keine absoluten Gelenkendpunkte.
