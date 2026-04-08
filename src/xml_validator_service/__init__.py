"""External XML Validator Service Integration.

Generic REST client for an external ISO 20022 validation service.
The actual provider is configurable; the module dispatches per
``pacs008_flavor`` to the correct endpoint path:

- CBPR+   -> POST /cbpr/validate
- TARGET2 -> POST /target2/validate (future)
- SEPA    -> POST /sepa/{scheme}/validate (future)

Credentials (Bearer token + base URL) are read from the gitignored
``xml_validator/`` folder at repo root, with fallback to environment
variables ``XML_VALIDATOR_API_KEY`` and ``XML_VALIDATOR_BASE_URL``.
"""
