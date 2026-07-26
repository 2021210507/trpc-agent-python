# Missing test rules

## Capability

`missing-tests` emits one low-confidence review candidate when changed
production Python has no changed Python test-file companion. It is a prompt for
human coverage review, never a high-confidence defect finding.

## Blind spots

The heuristic does not inspect existing coverage, non-Python tests, generated
tests, repository-specific test layouts, or behavioral relevance between a
production change and a test change.
