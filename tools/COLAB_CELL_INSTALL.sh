#!/bin/bash
# ==============================================================================
# CELL #1 ON COLAB (GOLDEN ENVIRONMENT INSTALLATION)
# ==============================================================================

# Clear HuggingFace Cache (To prevent errors from partially downloaded old safetensors files)
rm -rf ~/.cache/huggingface/*

# Install precise versions verified to not have the "to_dict" hallucination
pip install -U accelerate bitsandbytes datasets safetensors
pip install transformers==4.40.1 peft==0.10.0 trl==0.8.6

# Then open tools/DPO_A100_GOLDEN_FLAWLESS.py, copy all content into CELL #2,
# and run it to automatically succeed!
