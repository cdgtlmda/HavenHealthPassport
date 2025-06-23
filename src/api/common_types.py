"""Common GraphQL types to prevent circular dependencies.

This module contains shared GraphQL types that are used across multiple
API modules. Extracting these types prevents circular import issues.

In a medical system, clean architecture is critical for maintaining
reliability and preventing errors that could impact patient care.
"""

import graphene

from .types import Error, Verification


class VerificationPayload(graphene.ObjectType):
    """Payload for verification mutations.

    This payload is used to return verification results along with
    any errors that occurred during the verification process.
    """

    verification = graphene.Field(Verification)
    errors = graphene.List(Error)


class ConversionPayload(graphene.ObjectType):
    """Payload for conversion mutations."""

    result = graphene.JSONString()
    errors = graphene.List(Error)


class ValidationPayload(graphene.ObjectType):
    """Payload for validation mutations."""

    result = graphene.JSONString()
    errors = graphene.List(Error)


class FHIRTranslationPayload(graphene.ObjectType):
    """Payload for FHIR translation mutations."""

    result = graphene.JSONString()
    errors = graphene.List(Error)


class ClinicalDocumentTranslationPayload(graphene.ObjectType):
    """Payload for clinical document translation mutations."""

    result = graphene.JSONString()
    errors = graphene.List(Error)


class SectionTranslationPayload(graphene.ObjectType):
    """Payload for section translation mutations."""

    result = graphene.JSONString()
    errors = graphene.List(Error)
