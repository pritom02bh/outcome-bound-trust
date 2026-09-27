"""Frozen artifacts recorded for reproducibility (FIXES F5, F10, F12).

`EXTRACTOR_PROMPT_SHA256` pins obt.extractor.EXTRACTOR_SYSTEM. A test fails if
the prompt changes without updating this hash, so the prompt can't drift
silently after it is frozen (it is re-frozen once, after dev tuning in F10).
"""
EXTRACTOR_PROMPT_SHA256 = "ac1afafb1d267420db808b221dc59618475ddd687bebcc5c3ce34bf0885ad061"

# F10: the frozen message bank and extractor dataset (eval/build_message_bank.py). Runs refuse a bank whose
# sha256 differs; filled in when the bank is generated and committed.
MESSAGE_BANK_SHA256 = "09ab70e4b611ba4305a5f55be5a4d42756264b705ea5ee4c9f5b91e1f5245e7c"
EXTRACTOR_DATASET_SHA256 = "20ceb2459af9cac98b28558818e42da3fee444184fde090749ba6dd02a24e242"
