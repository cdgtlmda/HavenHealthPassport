"""Strawberry GraphQL Schema Definition.

This module creates the complete GraphQL schema for Haven Health Passport
by combining queries, mutations, and subscriptions.
"""

import strawberry

from src.api.strawberry_mutations import Mutation
from src.api.strawberry_queries import Query
from src.api.strawberry_subscriptions import Subscription

# Create the complete schema
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
)

# Export schema
__all__ = ["schema"]
