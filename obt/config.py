"""Frozen artifacts recorded for reproducibility (FIXES F5, F10, F12).

`EXTRACTOR_PROMPT_SHA256` pins obt.extractor.EXTRACTOR_SYSTEM. A test fails if
the prompt changes without updating this hash, so the prompt can't drift
silently after it is frozen (it is re-frozen once, after dev tuning in F10).
"""
EXTRACTOR_PROMPT_SHA256 = "ac1afafb1d267420db808b221dc59618475ddd687bebcc5c3ce34bf0885ad061"

# F10: the frozen message bank and extractor dataset (eval/build_message_bank.py). Runs refuse a bank whose
# sha256 differs; filled in when the bank is generated and committed.
MESSAGE_BANK_SHA256 = "69aa1e21407a32485bbc041274268e29e5c1241c94ee53a582d92772ec6f4a1e"
EXTRACTOR_DATASET_SHA256 = "1b1c39c48271d4d132a732288af274976755d083bcbc2c4111a13dcdae5d04b7"
