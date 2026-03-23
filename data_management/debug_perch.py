# debug_perch_attrs.py
import numpy as np
from perch_hoplite.zoo import model_configs

print("Loading Perch...")
base_model = model_configs.load_model_by_name('perch_v2')

print("Creating dummy audio...")
dummy = np.zeros(160000, dtype=np.float32)

print("Calling embed...")
result = base_model.embed(dummy)

print(f"\nType: {type(result)}")

# List all attributes and methods
print("\n--- Available attributes/methods ---")
attrs = [attr for attr in dir(result) if not attr.startswith('_')]
for attr in attrs:
    try:
        val = getattr(result, attr)
        print(f"  {attr}: {type(val).__name__}")
    except:
        print(f"  {attr}: <error>")

# Try common names for embedding access
print("\n--- Trying to access embeddings ---")
candidates = ['embeddings', 'embedding', 'output', 'scores', 'logits', 'numpy', 'value', 'data']

for candidate in candidates:
    if hasattr(result, candidate):
        val = getattr(result, candidate)
        print(f"✅ result.{candidate} found: {type(val)}")
        if hasattr(val, 'shape'):
            print(f"   shape: {val.shape}")
    else:
        print(f"❌ result.{candidate} not found")

# Try to convert via tf.identity
print("\n--- Trying TensorFlow conversion ---")
import tensorflow as tf
try:
    tf_tensor = tf.identity(result)
    print(f"✅ tf.identity worked: {type(tf_tensor)}")
    if hasattr(tf_tensor, 'numpy'):
        emb = tf_tensor.numpy()
        print(f"   numpy conversion worked, shape: {emb.shape}")
except Exception as e:
    print(f"❌ tf.identity failed: {e}")