# dataset_stats.py
import os

train = set(os.listdir('dataset/train'))
test = set(os.listdir('dataset/test'))

print(f"Train classes: {len(train)}")
print(f"Test classes: {len(test)}")

common = train & test
print(f"Common classes: {len(common)}")

only_test = test - train
print(f"Only in test: {len(only_test)}")

if only_test:
    print("\nFirst 10 species only in test:")
    for c in list(only_test)[:10]:
        print(f"  - {c}")