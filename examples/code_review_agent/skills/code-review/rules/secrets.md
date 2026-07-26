# Secret rules

## Capability

`secrets.*` uses the shared pattern table and entropy check to detect common
credentials in all text files. It scans new lines and deleted lines, retains
the real old-side location for deleted credentials, and redacts evidence with
the same pattern table before output.

## Blind spots

Split, encrypted, transformed, externally fetched, or nonstandard credentials
may not match. A placeholder-like value is intentionally suppressed to reduce
documentation noise, so it is not evidence that a secret store is configured.
