---
name: repo-wrapped
description: Make a Spotify Wrapped-style poster (SVG) and stats (JSON) of a git repository's history or of the user's own commits across many repos - commit personality, heatmap, power hours, languages, streaks. Use when the user asks for a year in review, git wrapped, commit stats, or a shareable picture of their coding year.
---

# repo-wrapped

One Python file, standard library only, reads `git log` locally. Nothing is uploaded.

## Commands (run from the repo folder)

```bash
python repo_wrapped.py path/to/repo                    # whole history -> repo-wrapped.svg
python repo_wrapped.py path/to/repo --year 2026        # one year
python repo_wrapped.py ~/code --year 2026              # every repo under ~/code, only your commits (git config user.email)
python repo_wrapped.py path/to/repo --author alice     # one author (regex on name/email)
python repo_wrapped.py path/to/repo --json             # all numbers
python repo_wrapped.py --demo                          # builds a deterministic demo repo and wraps it
```

## How to answer
1. Pick the scope from the question (one repo, a year, the user's own commits across folders).
2. Run it, then report the verdict line (for example "The Midnight Architect: 42% of commits after 10pm"), total commits and the longest streak.
3. Give the SVG path; it can go straight into a README with `![wrapped](repo-wrapped.svg)`.
