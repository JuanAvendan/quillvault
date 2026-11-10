# Changelog

All notable changes to this project are documented here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the
project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
