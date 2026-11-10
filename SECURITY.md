# Security policy & threat model

QuillVault processes images that may contain **health data** (sensitive personal data
under Colombian Law 1581 of 2012 and similar laws elsewhere). Its core promise:

> **Document images and recognised text never leave the machine they are processed on.**

## Reporting a vulnerability

Please **do not open a public issue**. Use GitHub's
[private vulnerability reporting](https://github.com/JuanAvendan/quillvault/security/advisories/new).
You will get an acknowledgement within 7 days. Never include real patient data in a report.

## Threat model

### Assets
Document images, recognised text, exported files, clipboard contents.

### In scope

| # | Threat | Mitigation | Where |
|---|---|---|---|
| T1 | Images or text sent to a third party | No cloud engines. VLM endpoint must resolve to loopback; `trust_env=False` ignores proxy variables. | `security/network.py`, `engines/vlm.py` |
| T2 | Silent network calls by dependencies | `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE`, telemetry switches set at import; Gradio analytics off, system fonts, no share links, no MCP/SSR servers. | `security/offline.py`, `ui/app.py` |
| T3 | Malicious input files (parser exploits, decompression bombs) | Magic-byte type check, extension allow-list, 50 MB file limit, 80 MP pixel limit, 100-page PDF limit, Pillow bomb protection. | `imaging/loader.py` |
| T4 | Tampered or malicious model weights | Models pinned to commit hashes; only `safetensors` downloaded; `local_files_only` at load time; downloads only via explicit `quillvault models download`. | `models.py`, `engines/trocr.py` |
| T5 | Sensitive data persisted on disk | UI uploads, previews and exports in a private temp dir, purged every 5 min and removed on exit. CLI never overwrites without `--overwrite`. | `security/tempfiles.py`, `ui/app.py` |
| T6 | Leakage through logs or tracebacks | Recognised text and filenames are never logged; redacting filter masks numbers, paths, e-mails; Typer tracebacks hide local variables; page IDs are content hashes. | `security/redaction.py`, `cli.py` |
| T7 | Clipboard history / cloud clipboard | Text is tagged `ExcludeClipboardContentFromMonitorProcessing`, `CanIncludeInClipboardHistory=0`, `CanUploadToCloudClipboard=0` and wiped after 45 s if unchanged. | `security/clipboard.py` |
| T8 | Network exposure of the review UI | Bound to `127.0.0.1` only; strict CORS; 50 MB upload limit. | `ui/app.py` |
| T9 | Real scans committed to Git | `.gitignore`, pre-commit hook and CI job block images/documents outside synthetic folders; gitleaks for secrets. | `scripts/check_sensitive_files.py` |
| T10 | Vulnerable dependencies | Locked dependencies (`uv.lock`), Dependabot, `pip-audit` and CodeQL in CI. | `.github/` |
| T11 | Silent "corrections" of clinical values | No automatic rewriting. Lexicon matches are suggestions; validators only flag; every VLM line is flagged for review. | `postprocess/` |

### Out of scope (your responsibility)

* **Data at rest on the host.** Deleting files does not wipe SSD blocks. Use full-disk
  encryption (BitLocker on Windows, LUKS on Linux).
* **A compromised operating system or user account.** Malware with the user's
  privileges can read anything QuillVault can.
* **Other users on a shared machine.** Use separate OS accounts.
* **Legal compliance.** QuillVault helps you minimise exposure; it does not certify
  compliance with Law 1581/2012, Resolution 1995/1999 or any other regulation.

## Hardening checklist for deployments

- [ ] BitLocker / LUKS enabled on the disk holding scans and exports
- [ ] Windows: *Clipboard history* and *Sync across devices* disabled (Settings → System → Clipboard)
- [ ] Scans deleted after review, according to your retention policy
- [ ] `quillvault doctor` shows *Offline mode* and *Telemetry disabled* as OK
- [ ] The machine is not shared, or each person has their own account
