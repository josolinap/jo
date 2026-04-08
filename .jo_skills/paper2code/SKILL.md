# paper2code: arXiv-to-Implementation Skill

> [!IMPORTANT]
> This skill is for turning academic papers into high-quality, citation-anchored code implementations.

## Principles

1. **Citation Anchoring**: Every non-trivial code decision must be anchored to a section, equation, or quote from the paper.
2. **Ambiguity Audit**: If a hyperparameter or architectural detail is missing, flag it as `[UNSPECIFIED]`. If you make a guess, flag it as `[ASSUMPTION]`.
3. **Traceability**: All generated code should be traceable back to the source paper logic.

## Workflow

1. **Paper Fetch**: Use `web_fetch` to read the paper (abstract + intro + architecture section).
2. **Ambiguity Audit**: List all parameters required for implementation. Mark which are specified in the paper and which are not.
3. **Draft Skeleton**: Create the file structure with §-comments.
4. **Implement**: Write the code using citation comments.

## Citation Convention

Use Python comments to link code to paper sections:

```python
# §3.2 — "We apply layer normalization before each sub-layer"
class TransformerBlock(nn.Module):
    def forward(self, x):
        # §3.2, Eq. 2 — attn_out = Softmax(QK^T / sqrt(d_k))
        attn_out = self.attention(self.norm1(x))
        x = x + attn_out # §3.3 — residual connection
```

## Flagging Convention

- `[UNSPECIFIED]`: Paper doesn't mention the value. "Using 1e-6 as default."
- `[ASSUMPTION]`: Paper is vague. "Assuming pre-norm based on §4.1 experimental results."
- `[FROM_OFFICIAL_CODE]`: If you cross-referenced a public repo.
