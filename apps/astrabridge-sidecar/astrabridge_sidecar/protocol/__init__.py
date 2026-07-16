"""AstraBridge cross-provider protocol ownership boundary.

The JSON Schema in :mod:`astrabridge_sidecar.protocol.schema.v1` is the sole
business-schema source. Generated Python/TypeScript projections live in the
separate ``protocol/generated`` and ``src/astrabridge_protocol/generated``
directories; existing graph and capability modules are compatibility bridges.
"""

from .generated.v1 import SCHEMA_ID, SCHEMA_VERSION, validate_protocol_payload

PROTOCOL_PACKAGE_OWNER = "astrabridge_sidecar.protocol"
PROTOCOL_SCHEMA_VERSION = SCHEMA_VERSION
PROTOCOL_SCHEMA_ID = SCHEMA_ID

__all__ = [
    "PROTOCOL_PACKAGE_OWNER",
    "PROTOCOL_SCHEMA_ID",
    "PROTOCOL_SCHEMA_VERSION",
    "validate_protocol_payload",
]
