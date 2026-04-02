# Verification Protocol

## Before Making Any Claim

### About Code:
`ash
git status
git diff
git log --oneline -5
`

### About Files:
`ash
ls -la [path]
cat [file] | head -20
`

### About System:
`ash
python self_check.py
`

## Rule: No Claims Without Evidence

If you cannot point to specific output from a command or content from a file, DO NOT make the claim.

## Example

WRONG: "The code was updated recently"
RIGHT: "git log shows commit abc123 from 2 hours ago"
