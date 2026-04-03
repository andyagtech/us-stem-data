# AI Classifier for Degree Type Inference

## Problem
22 universities have <20% degree labeling. The existing rule-based
`infer_degree_type()` function exhausts all available metadata fields.
For the remaining unlabeled records, the only information available is:
- Title of the thesis/dissertation
- Department/subject area
- Description (often truncated)

## Approach: Title-Based Classification

PhD dissertations and master's theses have different title patterns:

**PhD-like titles:**
- "A novel approach to..." (research contribution)
- "Investigation of..." / "Analysis of..."
- Long, specific titles (50+ chars)
- Technical methodology language

**MS-like titles:**
- "Design and implementation of..."
- Shorter, more applied titles
- "A study of..." / "An evaluation of..."

## Implementation Options

### Option A: Claude API Classification (Recommended)
Use Claude to classify titles in batch:

```python
# pipeline/step2b_ai_classify.py
import anthropic

def classify_degree_batch(titles: list[str]) -> list[str]:
    """Classify a batch of thesis titles as PhD or MS."""
    client = anthropic.Anthropic()
    
    prompt = f"""Classify each thesis/dissertation title as either PhD or MS (Master's).
PhD dissertations tend to be original research contributions.
Master's theses tend to be more applied or survey-oriented.
Reply with just "PhD" or "MS" for each, one per line.

Titles:
{chr(10).join(f'{i+1}. {t}' for i, t in enumerate(titles))}"""
    
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # Fast + cheap for classification
        max_tokens=len(titles) * 5,
        messages=[{"role": "user", "content": prompt}]
    )
    
    lines = response.content[0].text.strip().split('\n')
    return [line.strip().upper() for line in lines]
```

**Cost estimate:** 294K records × ~50 tokens/record = ~15M tokens.
At Haiku pricing (~$0.25/1M input): ~$4 total.

**Accuracy estimate:** ~85-90% based on title alone, higher with department context.

### Option B: Simple Heuristic Classifier
No API needed — use title length + keywords:

```python
def heuristic_classify(title: str, dept: str) -> str:
    """Simple heuristic: long research titles → PhD, short applied → MS."""
    t = title.lower()
    
    # Strong PhD signals
    if any(w in t for w in ['dissertation', 'doctoral', 'ph.d']):
        return 'phd'
    if any(w in t for w in ['master', 'thesis', 'm.s.']):
        return 'ms'
    
    # Length heuristic (PhD titles tend to be longer)
    if len(title) > 80:
        return 'phd'
    if len(title) < 40:
        return 'ms'
    
    return ''  # Uncertain
```

**Accuracy:** ~65-70%. Simple but imprecise.

### Option C: Train a Local Classifier
Use the 230K already-labeled records as training data:

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

# Use labeled records as training data
X_train = [r['title'] for r in labeled_records]
y_train = [r['degree'] for r in labeled_records]

vectorizer = TfidfVectorizer(max_features=5000)
X = vectorizer.fit_transform(X_train)
model = LogisticRegression().fit(X, y_train)

# Predict on unlabeled
X_unlabeled = vectorizer.transform([r['title'] for r in unlabeled_records])
predictions = model.predict(X_unlabeled)
```

**Accuracy:** ~80-85% with just titles, ~90%+ with title + department.
**Advantage:** Free, fast, reproducible. No API needed.

## Pipeline Integration

```
Step 2b: AI_CLASSIFY (optional, after PROCESS)
  Input:  data/processed/{key}.json with unlabeled records
  Output: data/processed/{key}.json with AI-classified labels
  Config: pipeline/ai_classify_config.json
    - method: "claude" | "sklearn" | "heuristic"
    - confidence_threshold: 0.85
    - mark_as: "ai_classified" (not "phd"/"ms" directly)
  
  Records get a new field:
    "degree": "phd",
    "degree_source": "ai_classifier",
    "degree_confidence": 0.92
```

## Recommendation
Start with **Option C (sklearn)** — it's free, fast, and uses our own
labeled data. We have 230K labeled records as training data, which is
more than enough for a good classifier. Add `degree_source` field to
distinguish AI-classified from metadata-derived labels.

If needed, use **Option A (Claude Haiku)** as a second pass for
records where sklearn confidence is low (<0.8).

## Display Considerations
- AI-classified records should show a subtle indicator (e.g., lighter
  badge color or dashed border) to distinguish from metadata-confirmed
- Tooltip: "Classified by AI based on title pattern (92% confidence)"
- Allow filtering by classification source
