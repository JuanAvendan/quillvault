# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- `quillvault templates --style notes` (new default): practice sheets are fictitious
  free-text consultation notes with common clinical abbreviations, one consistent
  note per page. The previous field-per-line sheets remain as `--style form`.
- Lexicon entries for frequent free-text words that were wrongly flagged.

### Fixed
- CI: mypy on Linux, dependency audit per GPU/CPU backend.

### Security
- Pillow forced to 13.0.0 (uv override; Gradio caps it below 13) to close ~40
  advisories in 12.x decoders. `Image.open` is pinned to the sniffed format.

## [0.1.0] - 2026-11-10

### Added
- OCR engines behind a common interface: RapidOCR (ONNX Runtime, DirectML GPU),
  TrOCR handwriting recogniser with RapidOCR line detection, local VLM via llama.cpp.
- Preprocessing: illumination flattening, deskew, ruled-line removal, CLAHE,
  optional binarisation and upscaling.
- Review policy: confidence threshold, date/ID/letter-digit validators, CIE-10
  extraction, medical lexicon suggestions (never automatic corrections).
- Local Gradio review UI with an editable line table, private copy and export.
- CLI: `extract`, `ui`, `benchmark`, `templates`, `models`, `doctor`.
- CER/WER benchmark that never outputs recognised text.
- Synthetic practice-sheet generator (fake clinical data, Faker `es_CO`).
- Security: offline mode, loopback-only VLM, safe file loading, pinned
  `safetensors` models, redacting logs, private temp dirs, history-excluded clipboard.
- CI (ruff, mypy strict, pytest on Windows/Linux), CodeQL, pip-audit, gitleaks,
  Dependabot, pre-commit hook that blocks scans and documents.
