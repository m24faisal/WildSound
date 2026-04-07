# step2_train_model.py
"""
STEP 2: FINE-TUNING THE AST AUDIO MODEL
- Loads your sliced WAV files.
- Fine-tunes Google's Audio Spectrogram Transformer.
- Saves the trained model to be converted for Android.
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
DATASET_DIR = Path("ai_training_dataset")
OUTPUT_MODEL_DIR = Path("my_custom_animal_model")

SAMPLE_RATE = 16000
MAX_DURATION = 3.0 # MUST match the chunk length from Step 1!

# Tell the model what your specific classes are
CLASS_LABELS = ["Bird", "Domestic", "Mammal", "Reptile_Amphibian"]
LABEL_TO_ID = {label: i for i, label in enumerate(CLASS_LABELS)}
ID_TO_LABEL = {i: label for label, i in LABEL_TO_ID.items()}

# ==========================================
# 1. LOAD THE PRE-TRAINED MODEL
# ==========================================
print("🧠 Loading pre-trained Google AudioSet model...")
feature_extractor = ASTFeatureExtractor.from_pretrained("MIT/ast-finetuned-audioset-10-10-0.4593")

# Load model and replace the final classification head with 4 outputs instead of 527
model = ASTForAudioClassification.from_pretrained(
    "MIT/ast-finetuned-audioset-10-10-0.4593", 
    num_labels=len(CLASS_LABELS),
    id2label=ID_TO_LABEL,
    label2id=LABEL_TO_ID,
    ignore_mismatched_sizes=True # Critical: Allows us to change the output size
)

# ==========================================
# 2. BUILD THE DATASET
# ==========================================
print("📂 Scanning dataset folder and converting audio to tensors...")

def audio_generator():
    """Reads WAV files and converts them to the format AST needs."""
    for class_folder in DATASET_DIR.iterdir():
        if not class_folder.is_dir():
            continue
        
        class_name = class_folder.name
        if class_name not in LABEL_TO_ID:
            continue
            
        label_id = LABEL_TO_ID[class_name]
        
        for wav_file in class_folder.glob("*.wav"):
            try:
                # Load audio
                y, sr = librosa.load(wav_file, sr=SAMPLE_RATE, mono=True)
                
                # Pad or truncate to exactly 3 seconds
                max_samples = int(MAX_DURATION * SAMPLE_RATE)
                if len(y) > max_samples:
                    y = y[:max_samples]
                elif len(y) < max_samples:
                    y = np.pad(y, (0, max_samples - len(y)), "constant")
                
                # Use feature extractor to convert to PyTorch tensor automatically
                inputs = feature_extractor(
                    y, 
                    sampling_rate=SAMPLE_RATE, 
                    return_tensors="pt"
                )
                
                # Yield the dictionary format Hugging Face expects
                yield {
                    "input_values": inputs["input_values"].squeeze(0).numpy(),
                    "labels": label_id
                }
            except Exception as e:
                print(f"Error loading {wav_file.name}: {e}")

# Create Hugging Face dataset directly from the generator
raw_dataset = Dataset.from_generator(audio_generator)

# Shuffle the dataset and split into 90% Training, 10% Testing
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

# Added type hints and fallback to satisfy VS Code's strict Pylance checker
def compute_metrics(eval_pred) -> dict:
    predictions, labels = eval_pred
    # AST returns logits, we need the highest number as our prediction
    predictions = np.argmax(predictions, axis=1)
    # Added "or {}" to guarantee it never returns None
    return accuracy.compute(predictions=predictions, references=labels) or {}

# ==========================================
# 4. TRAIN THE MODEL
# ==========================================
# Setup training arguments
training_args = TrainingArguments(
    output_dir="./training_checkpoints",
    eval_strategy="epoch",       # Evaluate at the end of every epoch
    save_strategy="epoch",       # Save at the end of every epoch
    learning_rate=5e-5,          # Standard fine-tuning learning rate
    per_device_train_batch_size=8, # Lower this to 4 if you get Out of Memory errors
    per_device_eval_batch_size=8,
    num_train_epochs=5,          # Run through the data 5 times
    weight_decay=0.01,
    logging_steps=10,
    load_best_model_at_end=True, # Keep the best version of the model
    metric_for_best_model="accuracy",
    remove_unused_columns=False, # Needed because of our custom generator
)

print("🏋️ Starting training...")
# Initialize the Hugging Face Trainer
# Using "processing_class" instead of "tokenizer" to bypass Pylance errors
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset["train"],
    eval_dataset=dataset["test"],
    processing_class=feature_extractor,
    compute_metrics=compute_metrics,
)

# Start the training loop!
trainer.train()

# ==========================================
# 5. SAVE THE FINAL MODEL
# ==========================================
print("\n💾 Saving trained model...")
OUTPUT_MODEL_DIR.mkdir(exist_ok=True)
trainer.save_model(str(OUTPUT_MODEL_DIR))
feature_extractor.save_pretrained(str(OUTPUT_MODEL_DIR))

print(f"🎉 TRAINING COMPLETE! Your custom model is saved in: ./{OUTPUT_MODEL_DIR}/")
print("You are now ready for Step 3 (Converting to TFLite for Android)!")