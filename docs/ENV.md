# Environment (F12)

Everything in the results was produced in this environment. Python packages are pinned exactly in
`requirements.lock` (`make lock` regenerates it from the venv). Each run record also stores its own
provenance (`meta`: git commit, config hash, model and digest, seed, message-bank, extractor-prompt and
dataset hashes, transport), so a table can always be traced to the code and inputs that made it.

## Machine
- macOS 27.0 (build 26A428), arm64, Apple M5, 32 GB RAM.
- Python 3.11.15 (`.venv`).

## Local models (ollama 0.18.0)
Full digests as reported by the ollama API (`obt.extractor.model_digest`); `ollama list` shows the first 12 hex digits.

| model | role | digest | architecture | parameters | quantization | context |
|---|---|---|---|---|---|---|
| `gpt-oss:20b` | extractor (all runs), LLM buyer | `17052f91a42e97930aa6e28a6c6c06a983e6a58dbb00434885a0cf5313e376f7` | gptoss | 20.9B | MXFP4 | 131072 |
| `qwen3:8b` | message-bank generator and semantic reader | `500a1f067a9f782620b40bee6f7b0c89e17ae61f686b92c24933e4ca4b2b8b41` | qwen3 | 8.2B | Q4_K_M | 40960 |

The extraction cache is keyed by model digest, so a re-pulled model never reuses stale answers.

## Frozen inputs (pinned in `obt/config.py`, checked by tests)
- Extractor prompt sha256 `ac1afafb…d061`.
- Message bank sha256 `09ab70e4…e7c`.
- Extractor dataset sha256 `20ceb245…e242`.

## Model checking
- TLC2 2.19 of 08 August 2024 (rev 5a47802), `tla2tools.jar` sha256 `936a2620…0e88`.
- OpenJDK 21.0.12.1 (portable, `tools/jdk-21.0.12.1+1`).

## Transport
- a2a-sdk 1.1.5 (JSON-RPC binding) on uvicorn and Starlette, localhost only (D25).

## Rebuilding
```
make test       # fast suite (no model calls, no TLC)
make results    # every table and figure, from runs/ only -> results/
```
