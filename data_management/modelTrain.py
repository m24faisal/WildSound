# step2_train_model.py
"""
STEP 2: FINE-TUNING THE AST AUDIO MODEL (DEBUG EDITION)
"""

import torch
from transformers import ASTFeatureExtractor, ASTForAudioClassification
from transformers import TrainingArguments, Trainer
from datasets import Dataset, DatasetDict
import librosa
import numpy as np
from pathlib import Path

# ==========================================
# CONFIGURATION
# ==========================================
# MAKE SURE THIS PATH MATCHES EXACTLY WHERE YOUR STEP 1 FOLDER IS!
DATASET_DIR = Path("ai_training_dataset") 
OUTPUT_MODEL_DIR = Path("my_custom_animal_model")

SAMPLE_RATE = 16000
MAX_DURATION = 3.0 

CLASS_LABELS = ["Bird", "Domestic", "Mammal", "Reptile_Amphibian"]
LABEL_TO_ID = {label: i for i, label in enumerate(CLASS_LABELS)}
ID_TO_LABEL = {i: label for label, i in LABEL_TO_ID.items()}

# ==========================================
# 1. LOAD THE PRE-TRAINED MODEL
# ==========================================
print("🧠 Loading pre-trained Google AudioSet model...")
feature_extractor = ASTFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")

model = ASTForAudioClassification.from_pretrained(
    "MIT/ast-finetuned-audioset-10-10-0.4593", 
    num_labels=len(CLASS_LABELS),
    ignore_mismatched_sizes=True 
)
model.config.id2label = ID_TO_LABEL
model.config.label2id = LABEL_TO_ID

# ==========================================
# 2. BUILD THE DATASET (DEBUG MODE)
# ==========================================
print(f"📂 Scanning folder: {DATASET_DIR.absolute()}")

# DEBUG CHECK: Let's see what the script actually sees inside the folder
if not DATASET_DIR.exists():
    print("❌ FATAL ERROR: The dataset folder does not exist! Check your path.")
    exit()
else:
    print("Found folders:")
    for item in DATASET_DIR.iterdir():
        print(f"  - {item.name}")

all_input_values = []
all_labels = []
file_count = 0

for class_folder in DATASET_DIR.iterdir():
    if not class_folder.is_dir():
        continue
    
    class_name = class_folder.name
    if class_name not in LABEL_TO_ID:
        print(f"⚠️ Skipping folder '{class_name}' (Not in CLASS_LABELS list)")
        continue
        
    label_id = LABEL_TO_ID[class_name]
    
    for wav_file in class_folder.glob("*.wav"):
        try:
            y, sr = librosa.load(wav_file, sr=SAMPLE_RATE, mono=True)
            
            max_samples = int(MAX_DURATION * SAMPLE_RATE)
            if len(y) > max_samples:
                y = y[:max_samples]
            elif len(y) < max_samples:
                y = np.pad(y, (0, max_samples - len(y)), "constant")
            
            inputs = feature_extractor(
                y, 
                sampling_rate=SAMPLE_RATE, 
                return_tensors="pt"
            )
            
            all_input_values.append(inputs["input_values"].squeeze(0).numpy())
            all_labels.append(label_id)
            file_count += 1
            
            if file_count % 100 == 0:
                print(f"   Loaded {file_count} files...")
                
        except Exception as e:
            # CHANGED FROM 'pass' TO 'print' SO WE CAN SEE WHY FILES ARE SKIPPED
            print(f"❌ SKIPPED {wav_file.name}: {e}")

print(f"✅ Successfully loaded {file_count} files into memory.")

if file_count == 0:
    print("❌ FATAL ERROR: No files were loaded. Please read the errors above.")
    exit()

print("Formatting dataset...")
raw_dataset = Dataset.from_dict({
    "input_values": all_input_values,
    "labels": all_labels
})

raw_dataset = raw_dataset.shuffle(seed=42)
split = raw_dataset.train_test_split(test_size=0.1, seed=42)
dataset = DatasetDict({
    "train": split["train"],
    "test": split["test"]
})

print(f"✅ Dataset ready! {len(dataset['train'])} training files, {len(dataset['test'])} testing files.")

# ==========================================
# 3. DEFINE METRICS
# ==========================================
import evaluate
accuracy = evaluate.load("accuracy")

def compute_metrics(eval_pred) -> dict:
    predictions, labels = eval_pred
    predictions = np.argmax(predictions, axis=1)
    return accuracy.compute(predictions=predictions, references=labels) or {}

# ==========================================
# 4. TRAIN THE MODEL
# ==========================================
training_args = TrainingArguments(
    output_dir="./training_checkpoints",
    eval_strategy="epoch",       
    save_strategy="epoch",       
    learning_rate=5e-5,          
    per_device_train_batch_size=8, 
    per_device_eval_batch_size=8,
    num_train_epochs=5,          
    weight_decay=0.01,
    logging_steps=10,
    load_best_model_at_end=True, 
    metric_for_best_model="accuracy",
    remove_unused_columns=False, 
)

print("🏋️ Starting training...")

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["test"],
    processing_class=feature_extractor,
    compute_metrics=compute_metrics,
)

trainer.train()

# ==========================================
# 5. SAVE THE FINAL MODEL
# ==========================================
print("\n💾 Saving trained model...")
OUTPUT_MODEL_DIR.mkdir(exist_ok=True)
trainer.save_model(str(OUTPUT_MODEL_DIR))
feature_extractor.save_pretrained(str(OUTPUT_MODEL_DIR))

print(f"🎉 TRAINING COMPLETE! Your custom model is saved in: ./{OUTPUT_MODEL_DIR}/")