"""
Campus Resolve - AI/ML Category Classifier (classifier.py)
Text Preprocessing, TF-IDF Vectorization, and Multinomial Naive Bayes.
High-precision text classification for campus grievances.
"""

import os
import json
import math
import re
from collections import Counter, defaultdict

# Built-in lightweight English stop words
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'aren',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by',
    'can', 'could', 'did', 'do', 'does', 'doing', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'has', 'have', 'having', 'he', 'her', 'here', 'hers', 'herself', 'him', 'himself',
    'his', 'how', 'i', 'if', 'in', 'into', 'is', 'isn', 'it', 'its', 'itself', 'just', 'me', 'more',
    'most', 'my', 'myself', 'no', 'nor', 'not', 'now', 'of', 'off', 'on', 'once', 'only', 'or', 'other',
    'our', 'ours', 'ourselves', 'out', 'over', 'own', 's', 'same', 'she', 'should', 'so', 'some', 'such',
    't', 'than', 'that', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'these', 'they',
    'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasn', 'we', 'were',
    'what', 'when', 'where', 'which', 'while', 'who', 'whom', 'why', 'will', 'with', 'won', 'would', 'you'
}

CATEGORIES = [
    "Electrical",
    "Cleaning",
    "Internet",
    "Classroom Equipment",
    "Plumbing",
    "Other"
]

def preprocess_text(text):
    """
    Cleans, normalizes, and tokenizes complaint text.
    - Converts to lowercase
    - Strips special characters and punctuation
    - Filters out stop words and short noise
    """
    if not text:
        return []
    clean = re.sub(r'[^a-zA-Z0-9\s]', ' ', text.lower())
    tokens = clean.split()
    return [w for w in tokens if w not in STOP_WORDS and len(w) > 2]

class CampusComplaintClassifier:
    """
    Text Classifier utilizing TF-IDF Vectorization and Multinomial Naive Bayes.
    """
    def __init__(self, alpha=0.1):
        self.alpha = alpha
        self.categories = list(CATEGORIES)
        self.vocabulary = {} # word -> index
        self.idf = {} # word -> idf value
        self.class_priors = {} # category -> log P(C)
        self.feature_log_probs = {} # category -> {word: log P(w|C)}
        self.is_trained = False

    def train(self, documents, labels):
        """
        Trains the TF-IDF Vectorizer and Multinomial Naive Bayes model.
        - documents: list of text strings
        - labels: list of category strings
        """
        n_docs = len(documents)
        if n_docs == 0:
            return

        # 1. Tokenize all documents
        tokenized_docs = [preprocess_text(doc) for doc in documents]
        
        # 2. Build vocabulary and Document Frequency (DF)
        doc_freq = Counter()
        all_words = set()
        for doc_tokens in tokenized_docs:
            unique_in_doc = set(doc_tokens)
            for w in unique_in_doc:
                doc_freq[w] += 1
                all_words.add(w)
                
        self.vocabulary = {w: i for i, w in enumerate(sorted(all_words))}
        vocab_size = len(self.vocabulary)
        
        # 3. Calculate Smooth Inverse Document Frequency: idf(w) = ln((1 + N) / (1 + df(w))) + 1
        self.idf = {}
        for w, df in doc_freq.items():
            self.idf[w] = math.log((1.0 + n_docs) / (1.0 + df)) + 1.0

        # 4. Class counts and Priors: P(C) = N_c / N
        class_counts = Counter(labels)
        self.class_priors = {
            c: math.log(class_counts.get(c, 1) / n_docs)
            for c in self.categories
        }

        # 5. Compute word TF-IDF weights per category
        category_word_weights = {c: defaultdict(float) for c in self.categories}
        category_total_weights = {c: 0.0 for c in self.categories}
        
        for doc_tokens, cat in zip(tokenized_docs, labels):
            tf = Counter(doc_tokens)
            for w, count in tf.items():
                if w in self.idf:
                    weight = count * self.idf[w]
                    category_word_weights[cat][w] += weight
                    category_total_weights[cat] += weight

        # 6. Multinomial Naive Bayes likelihoods with Laplace/Lidstone smoothing
        # log P(w|C) = log( (weight(w, C) + alpha) / (total_weight(C) + alpha * vocab_size) )
        self.feature_log_probs = {}
        for c in self.categories:
            self.feature_log_probs[c] = {}
            denom = category_total_weights[c] + (self.alpha * vocab_size)
            for w in self.vocabulary:
                num = category_word_weights[c].get(w, 0.0) + self.alpha
                self.feature_log_probs[c][w] = math.log(num / denom)
                
        self.is_trained = True

    def predict(self, text):
        """
        Predicts category, confidence, and all category probabilities.
        Returns:
            (predicted_category, confidence_float, probabilities_dict)
        """
        if not self.is_trained:
            return "Other", 0.0, {c: 0.0 for c in self.categories}

        tokens = preprocess_text(text)
        if not tokens:
            return "Other", 0.0, {c: 1.0 / len(self.categories) for c in self.categories}

        # Filter known vocabulary
        known_tokens = [w for w in tokens if w in self.vocabulary]
        if not known_tokens:
            return "Other", 0.16, {c: 1.0 / len(self.categories) for c in self.categories}

        # Compute log posteriors for each class: log P(C) + sum(tf * idf * log P(w|C))
        tf = Counter(known_tokens)
        log_posteriors = {}
        
        for c in self.categories:
            score = self.class_priors[c]
            for w, count in tf.items():
                tfidf_w = count * self.idf.get(w, 1.0)
                score += tfidf_w * self.feature_log_probs[c][w]
            log_posteriors[c] = score

        # Numerical stability: subtract max before exponentiating (Log-Sum-Exp)
        max_log = max(log_posteriors.values())
        exp_scores = {c: math.exp(score - max_log) for c, score in log_posteriors.items()}
        sum_exp = sum(exp_scores.values()) or 1.0
        
        probabilities = {c: exp_scores[c] / sum_exp for c in self.categories}
        
        # Pick best category
        best_category = max(probabilities, key=probabilities.get)
        confidence = probabilities[best_category]

        return best_category, round(confidence, 4), {c: round(p, 4) for c, p in probabilities.items()}

    def save_model(self, file_path):
        """Saves model weights, idf tables, and vocabulary to JSON."""
        data = {
            "alpha": self.alpha,
            "categories": self.categories,
            "vocabulary": self.vocabulary,
            "idf": self.idf,
            "class_priors": self.class_priors,
            "feature_log_probs": self.feature_log_probs
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load_model(self, file_path):
        """Loads model from JSON file."""
        if not os.path.exists(file_path):
            return False
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            self.alpha = data.get("alpha", 0.1)
            self.categories = data.get("categories", CATEGORIES)
            self.vocabulary = data.get("vocabulary", {})
            self.idf = data.get("idf", {})
            self.class_priors = data.get("class_priors", {})
            self.feature_log_probs = data.get("feature_log_probs", {})
            self.is_trained = True
            return True

# Global model instance
_model_instance = None

def get_classifier():
    """Returns singleton loaded classifier instance."""
    global _model_instance
    if _model_instance is None:
        _model_instance = CampusComplaintClassifier()
        model_path = os.path.join(os.path.dirname(__file__), "trained_model.json")
        if os.path.exists(model_path):
            _model_instance.load_model(model_path)
    return _model_instance

def predict_complaint_category(text):
    """
    Convenience function for category prediction with graceful fallback.
    Returns:
        dict: {
            "category": "Electrical",
            "confidence": 0.89,
            "status": "success" | "fallback",
            "scores": { ... }
        }
    """
    if not text or len(text.strip()) < 5:
        return {
            "category": "Other",
            "confidence": 0.0,
            "status": "fallback",
            "scores": {c: 0.0 for c in CATEGORIES}
        }
    
    classifier = get_classifier()
    if not classifier.is_trained:
        return {
            "category": "Other",
            "confidence": 0.0,
            "status": "fallback",
            "scores": {c: 0.0 for c in CATEGORIES}
        }

    category, conf, scores = classifier.predict(text)
    return {
        "category": category,
        "confidence": conf,
        "status": "success",
        "scores": scores
    }
