# diagnose_failed.py
import os
import soundfile as sf
from tqdm import tqdm

test_path = 'dataset/test'
failed_files = []
successful_files = []

for class_name in tqdm(os.listdir(test_path)):
    class_dir = os.path.join(test_path, class_name)
    if not os.path.isdir(class_dir):
        continue
    for file in os.listdir(class_dir):
        if file.endswith(('.wav', '.mp3')):
            file_path = os.path.join(class_dir, file)
            try:
                audio, sr = sf.read(file_path)
                if len(audio) == 0:
                    failed_files.append((file_path, "Empty audio"))
                else:
                    successful_files.append(file_path)
            except Exception as e:
                failed_files.append((file_path, str(e)[:50]))

print(f"Successful: {len(successful_files)}")
print(f"Failed: {len(failed_files)}")

if failed_files:
    print("\nFirst 10 failed files:")
    for path, err in failed_files[:10]:
        print(f"  {os.path.basename(path)}: {err}")