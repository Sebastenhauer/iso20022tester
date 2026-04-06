"""FINaplo API integration (Payment Components).

Uses Bearer auth + per-flavor endpoint dispatch:
- CBPR+  -> POST /cbpr/validate
- TARGET2 -> POST /target2/validate (future)
- SEPA   -> POST /sepa/{scheme}/validate (future)

Credentials are read from the gitignored ``finaplo/`` folder at repo root.
"""
