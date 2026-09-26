"""Frozen artifacts recorded for reproducibility (FIXES F5, F10, F12).

`EXTRACTOR_PROMPT_SHA256` pins obt.extractor.EXTRACTOR_SYSTEM. A test fails if
the prompt changes without updating this hash, so the prompt can't drift
silently after it is frozen (it is re-frozen once, after dev tuning in F10).
"""
EXTRACTOR_PROMPT_SHA256 = "ac1afafb1d267420db808b221dc59618475ddd687bebcc5c3ce34bf0885ad061"

# F10: the frozen message bank and extractor dataset (eval/build_message_bank.py). Runs refuse a bank whose
# sha256 differs; filled in when the bank is generated and committed.
MESSAGE_BANK_SHA256 = "bcc8852227dd348ced350a4b7a840035e82c7d4ce454e0bd5d6503fd69043ab3"
EXTRACTOR_DATASET_SHA256 = "711dc7430d090e0c4c8748cba6fd421c80c81d477fb703437e853c3e0e5e70ef"
