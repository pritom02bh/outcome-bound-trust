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

# E2b (D30): the frozen "trust-aware" buyer view variant (obt.memory_view.TRUST_AWARE_OBT + TRUST_AWARE_REP).
BUYER_TRUST_AWARE_SHA256 = "490aa22eac5d66925d01b9fc370b7a11f546805cdde6a90a028b9975afc5fa78"

# E8 (D43): the frozen LLM-adversary prompts (obt.attacks.llm_adversary). White-box covers the template and every
# defense description. Frozen before any E8 run; a test fails if either prompt changes without updating these.
ATTACKER_BLACKBOX_SHA256 = "404c4deeab4cee5b825ca8c6d6ee22f94f54c6f2ea04ef11497cbb58803de795"
ATTACKER_WHITEBOX_SHA256 = "5908a3f4efe26f0ec3314d291e2d72cb1cd6dd21d65a2f4d336a763018ccbddc"
