"""AstraBridge cross-provider protocol ownership boundary.

This package is the migration target for versioned schemas, immutable Agent
Envelopes, delivery events, and artifact references. Existing graph and
capability modules remain compatibility bridges until the stability execution
plan migrates each consumer behind these boundaries.
"""

PROTOCOL_PACKAGE_OWNER = "astrabridge_sidecar.protocol"
PROTOCOL_SCHEMA_VERSION = "astrabridge-protocol-boundary-v1"

__all__ = ["PROTOCOL_PACKAGE_OWNER", "PROTOCOL_SCHEMA_VERSION"]
