"""
Campus Resolve - Model Training Script (train_model.py)
Loads dataset, performs train/test split, trains Multinomial Naive Bayes classifier,
evaluates precision, recall, and accuracy, and serializes the model.
"""

import os
import json
import random
from collections import defaultdict
from classifier import CampusComplaintClassifier, CATEGORIES

def load_dataset(dataset_path):
    with open(dataset_path, "r", encoding="utf-8") as f:
        return json.load(f)

def train_test_split(data, test_ratio=0.2, seed=42):
    random.seed(seed)
    shuffled = list(data)
    random.shuffle(shuffled)
    split_idx = int(len(shuffled) * (1 - test_ratio))
    return shuffled[:split_idx], shuffled[split_idx:]

def evaluate(model, test_data):
    """Computes real Accuracy, Precision, Recall, and F1-Score per category."""
    if not test_data:
        return {}

    correct = 0
    total = len(test_data)
    
    tp = defaultdict(int)
    fp = defaultdict(int)
    fn = defaultdict(int)

    for item in test_data:
        pred_cat, _, _ = model.predict(item["text"])
        actual_cat = item["category"]
        
        if pred_cat == actual_cat:
            correct += 1
            tp[actual_cat] += 1
        else:
            fp[pred_cat] += 1
            fn[actual_cat] += 1

    accuracy = correct / total if total > 0 else 0.0

    metrics = {
        "accuracy": round(accuracy, 4),
        "total_test_samples": total,
        "correct_predictions": correct,
        "per_category": {}
    }

    for cat in CATEGORIES:
        true_pos = tp[cat]
        false_pos = fp[cat]
        false_neg = fn[cat]

        prec = true_pos / (true_pos + false_pos) if (true_pos + false_pos) > 0 else 0.0
        rec = true_pos / (true_pos + false_neg) if (true_pos + false_neg) > 0 else 0.0
        f1 = (2 * prec * rec) / (prec + rec) if (prec + rec) > 0 else 0.0

        metrics["per_category"][cat] = {
            "precision": round(prec, 4),
            "recall": round(rec, 4),
            "f1_score": round(f1, 4)
        }

    return metrics

def run_training():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_file = os.path.join(base_dir, "dataset.json")
    model_output_file = os.path.join(base_dir, "trained_model.json")

    print("=" * 60)
    print("CAMPUS RESOLVE - AI/ML CATEGORY CLASSIFIER TRAINING")
    print("=" * 60)

    print(f"Loading dataset from: {dataset_file}")
    data = load_dataset(dataset_file)
    print(f"Total labeled complaint records: {len(data)}")

    # 80/20 train/test split
    train_data, test_data = train_test_split(data, test_ratio=0.2, seed=42)
    print(f"Training samples: {len(train_data)} | Testing samples: {len(test_data)}")

    # Initialize and train model
    model = CampusComplaintClassifier(alpha=1.0)
    train_texts = [d["text"] for d in train_data]
    train_labels = [d["category"] for d in train_data]

    print("\nTraining TF-IDF Vectorizer and Multinomial Naive Bayes model...")
    model.train(train_texts, train_labels)
    print(f"Vocabulary size: {len(model.vocabulary)} unique tokens")

    # Evaluate on test set
    print("\nEvaluating on unseen test set...")
    metrics = evaluate(model, test_data)
    print(f"Actual Test Accuracy: {metrics['accuracy'] * 100:.1f}% ({metrics['correct_predictions']}/{metrics['total_test_samples']} correct)")
    print("-" * 60)
    print(f"{'Category':<22} | {'Precision':<10} | {'Recall':<10} | {'F1-Score':<10}")
    print("-" * 60)
    for cat, vals in metrics["per_category"].items():
        print(f"{cat:<22} | {vals['precision']:<10.2f} | {vals['recall']:<10.2f} | {vals['f1_score']:<10.2f}")
    print("-" * 60)

    # Train on full dataset for production serialization
    print("\nTraining production model on 100% of labeled data...")
    prod_model = CampusComplaintClassifier(alpha=0.1)
    prod_model.train([d["text"] for d in data], [d["category"] for d in data])
    prod_model.save_model(model_output_file)
    print(f"Production model successfully serialized to: {model_output_file} (Vocab size: {len(prod_model.vocabulary)})")

    # Test sample predictions with production model
    sample_queries = [
        "The ceiling fan is stopped and socket sparked in classroom 104",
        "Wi-Fi connection is dropping every minute in the main library",
        "Washroom tap is leaking and overflowing on second floor",
        "Spilled dust and overflowing garbage bin outside dining area",
        "Ceiling projector HDMI cable bent and screen not displaying",
        "Stray aggressive dog roaming near campus entrance gate"
    ]
    print("\nSample Real-World Inferences:")
    for query in sample_queries:
        cat, conf, _ = prod_model.predict(query)
        print(f" - Query: '{query}'")
        print(f"   -> Suggested Category: {cat} (Confidence: {conf*100:.1f}%)\n")

    print("AI/ML training pipeline finished successfully.")
    return metrics

if __name__ == "__main__":
    run_training()
