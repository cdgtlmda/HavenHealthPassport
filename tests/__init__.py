"""Haven Health Passport Test Suite.

Medical-compliant testing for refugee healthcare system

This test suite enforces:
- FHIR R4 compliance for all healthcare resources
- HIPAA compliance for PHI handling
- Zero unencrypted PHI on blockchain
- Complete audit trails for all PHI access
- Emergency access protocols
- Offline operation for disconnected refugee camps
"""

__version__ = "1.0.0"
__compliance__ = {
    "fhir": "R4",
    "hipaa": "2024",
    "blockchain": "hash-only",
    "encryption": "AES-256-GCM",
}
