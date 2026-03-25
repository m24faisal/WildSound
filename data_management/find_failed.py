# find_failed.py
import os

test_path = 'dataset/test'
failed = []

for root, dirs, files in os.walk(test_path):
    for file in files:
        if file.endswith('.mp3'):
            # If an MP3 still exists, it wasn't converted
            failed.append(os.path.join(root, file))

print(f"Remaining MP3 files: {len(failed)}")
for f in failed:
    print(f"  {f}")