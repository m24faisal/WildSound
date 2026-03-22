#!/usr/bin/env python3
"""
Wild Sound - Perch 2.0 Embedding Extraction
Correct way to handle InferenceOutputs from Perch
"""

import numpy as np
from perch_hoplite.zoo import model_configs

print("Loading Perch 2.0 model...")
base_model = model_configs.load_model_by_name('perch_v2')
print("✅ Model loaded")

# Create a dummy audio (5 seconds of silence at 32kHz)
dummy_audio = np.zeros(160000, dtype=np.float32)

print("\nCalling embed() on dummy audio...")
result = base_model.embed(dummy_audio)

print(f"\nResult type: {type(result)}")
print(f"Result: {result}")

# Convert to numpy - this works!
embeddings_np = np.array(result)
print(f"\n✅ Converted to numpy, shape: {embeddings_np.shape}")
print(f"   First 5 values: {embeddings_np.flatten()[:5]}")