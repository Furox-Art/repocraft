# What does this PR change?

<!-- One paragraph. Link the issue it closes, if there is one. -->

# What a reviewer should check first

<!-- Name the one thing that would make this wrong. -->

# Checklist

- [ ] `python -m ruff check .`, `python -m mypy`, and the pytest suite pass with
      100% branch coverage
- [ ] Golden snapshots changed only where the template change was intentional,
      and every changed golden file was reviewed
- [ ] Deterministic paths (`validate`, `render`, `recipes`, `make`) still make no
      model or network calls
- [ ] The same input still produces byte-identical output, or the PR says which
      axis of the determinism matrix changed and why
- [ ] README and CHANGELOG describe the new behavior
- [ ] A new or changed recipe ships its tests and stays standard-library only
