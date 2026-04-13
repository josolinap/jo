# Paper2Code - Research to Implementation Protocol

When asked to implement code from a research paper (arxiv, academic paper, etc.), follow this protocol:

## Before Writing Any Code

1. **Fetch and parse the paper** - Get the full paper content including appendices
2. **Identify core contributions** - What specifically does this paper contribute?
3. **Check for official code** - Search for official implementation before generating

## Citation Anchoring System

Every non-trivial code decision MUST reference the paper:

```python
# §3.2 — "We apply layer normalization before each sub-layer" (Pre-LN variant)
class TransformerBlock(nn.Module):
    def forward(self, x):
        # §3.2, Eq. 2 — attention_weights = softmax(QK^T / sqrt(d_k))
        attn_out = self.attention(self.norm1(x))
        x = x + attn_out  # §3.2 — residual connection
```

## Ambiguity Classification

| Tag | Meaning |
|-----|---------|
| `§X.Y` | Directly specified in paper section X.Y |
| `§X.Y, Eq. N` | Implements equation N from section X.Y |
| `[UNSPECIFIED]` | Paper does not state this — choice with alternatives listed |
| `[PARTIALLY_SPECIFIED]` | Paper mentions but ambiguous — quote included |
| `[ASSUMPTION]` | Reasonable inference — reasoning explained |
| `[FROM_OFFICIAL_CODE]` | Taken from authors' official implementation |

## UNSPECIFIED Flag System

When paper doesn't specify something:

```python
# [UNSPECIFIED] Paper does not state epsilon for LayerNorm — using 1e-6 (common default)
# Alternatives: 1e-5 (PyTorch default), 1e-8 (some implementations)
self.norm = nn.LayerNorm(d_model, eps=1e-6)
```

```python
# [ASSUMPTION] Using pre-norm based on "we found pre-norm more stable" in §4.1
# The paper uses post-norm in Figure 1 but pre-norm in experiments — ambiguous
```

## Output Structure

For each paper implementation, generate:

```
{paper_slug}/
├── README.md                    # Paper summary, contribution statement, quick-start
├── REPRODUCTION_NOTES.md        # Ambiguity audit, unspecified choices, known deviations
├── requirements.txt             # Pinned dependencies
├── src/
│   ├── model.py                 # Architecture — each class cited to paper section
│   ├── loss.py                  # Loss functions with equation references
│   ├── data.py                  # Dataset class skeleton with preprocessing TODOs
│   ├── train.py                 # Training loop (if in scope)
│   ├── evaluate.py              # Metric computation code
│   └── utils.py                 # Shared utilities
├── configs/
│   └── base.yaml                # All hyperparams — each cited or flagged [UNSPECIFIED]
└── notebooks/
    └── walkthrough.ipynb        # Pedagogical notebook
```

## Key Principles

1. **NEVER silently fill gaps** - Always flag unspecified choices
2. **Cite every decision** - Reference paper sections/equations
3. **Check appendices** - Appendices are first-class sources
4. **Don't implement baselines** - Only core contributions
5. **Don't reimplement standards** - Import standard components

## Usage

When implementing from paper:
```
/paper2code https://arxiv.org/abs/XXXX.XXXXX
```

Or with framework:
```
/paper2code 1706.03762 --framework pytorch
```
