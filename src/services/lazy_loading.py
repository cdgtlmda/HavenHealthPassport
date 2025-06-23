"""Lazy loading implementation for database queries.

This module provides lazy loading capabilities for SQLAlchemy models
to optimize database performance by loading related data only when needed.
"""

from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Type, cast

from sqlalchemy import inspect
from sqlalchemy.orm import (
    Query,
    RelationshipProperty,
    Session,
    defer,
    joinedload,
    lazyload,
    noload,
    selectinload,
    subqueryload,
)
from sqlalchemy.orm.strategy_options import Load

from src.utils.logging import get_logger

logger = get_logger(__name__)


class LazyLoadingStrategy:
    """Strategies for lazy loading relationships."""

    # Load strategies
    LAZY = "lazy"  # Default lazy loading
    EAGER = "eager"  # Eager loading with join
    SUBQUERY = "subquery"  # Load with separate query
    SELECTIN = "selectin"  # Load with IN query
    JOINED = "joined"  # Load with JOIN
    NOLOAD = "noload"  # Don't load

    @classmethod
    def get_loader(cls, strategy: str) -> Callable:
        """Get SQLAlchemy loader for strategy."""
        loaders = {
            cls.LAZY: lazyload,
            cls.EAGER: joinedload,
            cls.SUBQUERY: subqueryload,
            cls.SELECTIN: selectinload,
            cls.JOINED: joinedload,
            cls.NOLOAD: noload,
        }
        loader = loaders.get(strategy, lazyload)
        return cast(Callable, loader)


class LazyLoadingMixin:
    """Mixin for models to support lazy loading configuration."""

    # Default loading strategy for relationships
    _default_loading_strategy = LazyLoadingStrategy.LAZY

    # Relationship loading configuration
    _relationship_loading: Dict[str, str] = {}

    @classmethod
    def configure_loading(
        cls,
        relationship_name: str,
        strategy: str = LazyLoadingStrategy.LAZY,
    ) -> None:
        """Configure loading strategy for a relationship.

        Args:
            relationship_name: Name of the relationship attribute
            strategy: Loading strategy to use
        """
        cls._relationship_loading[relationship_name] = strategy
        logger.debug(f"Configured {relationship_name} with {strategy} loading")

    @classmethod
    def with_loaded(cls, *relationships: str) -> Load:
        """Create query options to load specific relationships.

        Args:
            relationships: Names of relationships to load

        Returns:
            SQLAlchemy Load options
        """
        options = []
        for rel in relationships:
            strategy = cls._relationship_loading.get(rel, cls._default_loading_strategy)
            loader = LazyLoadingStrategy.get_loader(strategy)
            options.append(loader(getattr(cls, rel)))

        return options  # type: ignore[return-value]

    @classmethod
    def query_with_options(
        cls,
        session: Session,
        load_relationships: Optional[List[str]] = None,
        defer_columns: Optional[List[str]] = None,
    ) -> Query:
        """Create a query with specific loading options.

        Args:
            session: Database session
            load_relationships: Relationships to load
            defer_columns: Columns to defer loading

        Returns:
            Configured query
        """
        query = session.query(cls)

        # Apply relationship loading
        if load_relationships:
            for rel in load_relationships:
                strategy = cls._relationship_loading.get(
                    rel, cls._default_loading_strategy
                )
                loader = LazyLoadingStrategy.get_loader(strategy)
                query = query.options(loader(getattr(cls, rel)))

        # Apply column deferral
        if defer_columns:
            for col in defer_columns:
                query = query.options(defer(getattr(cls, col)))

        return query

    def load_relationship(
        self,
        relationship_name: str,
        session: Optional[Session] = None,
    ) -> Any:
        """Explicitly load a relationship.

        Args:
            relationship_name: Name of relationship to load
            session: Database session (uses object session if not provided)
        """
        if not session:
            inspection = inspect(self)
            if inspection and inspection.session:
                session = inspection.session

        if not session:
            raise ValueError("No session available for loading")

        # Force load the relationship
        rel = getattr(self, relationship_name)
        if hasattr(rel, "all"):
            # It's a collection
            _ = rel.all()
        else:
            # It's a single object
            _ = rel


def lazy_property(
    load_on_access: bool = True,
    cache_result: bool = True,
    expire_on_commit: bool = True,  # pylint: disable=unused-argument
) -> Callable[[Callable], property]:
    """Create lazy-loaded properties.

    Args:
        load_on_access: Load data when property is accessed
        cache_result: Cache the loaded result
        expire_on_commit: Expire cache on session commit (reserved for future use)
    """

    def decorator(func: Callable) -> property:
        attr_name = f"_lazy_{func.__name__}"

        @wraps(func)
        def getter(self: Any) -> Any:
            # Check if already loaded
            if cache_result and hasattr(self, attr_name):
                return getattr(self, attr_name)

            # Load the data
            if load_on_access:
                result = func(self)

                # Cache if enabled
                if cache_result:
                    setattr(self, attr_name, result)

                return result

            return None

        @wraps(func)
        def setter(self: Any, value: Any) -> None:
            setattr(self, attr_name, value)

        @wraps(func)
        def deleter(self: Any) -> None:
            if hasattr(self, attr_name):
                delattr(self, attr_name)

        return property(getter, setter, deleter)

    return decorator


class LazyLoader:
    """Utility class for lazy loading configuration."""

    def __init__(self, model_class: Type[Any]):
        """Initialize lazy loader for a model class.

        Args:
            model_class: SQLAlchemy model class
        """
        self.model_class = model_class
        self.mapper = inspect(model_class)
        self.relationships = self._get_relationships()
        self.columns = self._get_columns()

    def _get_relationships(self) -> Dict[str, RelationshipProperty]:
        """Get all relationships for the model."""
        return {key: rel for key, rel in self.mapper.relationships.items()}

    def _get_columns(self) -> List[str]:
        """Get all column names for the model."""
        return [col.key for col in self.mapper.columns]

    def create_loading_options(
        self,
        include_relationships: Optional[List[str]] = None,
        exclude_relationships: Optional[List[str]] = None,
        defer_columns: Optional[List[str]] = None,
        strategy_overrides: Optional[Dict[str, str]] = None,
    ) -> List[Any]:
        """Create SQLAlchemy loading options.

        Args:
            include_relationships: Relationships to include
            exclude_relationships: Relationships to exclude
            defer_columns: Columns to defer loading
            strategy_overrides: Override loading strategies

        Returns:
            List of SQLAlchemy options
        """
        options = []
        strategy_overrides = strategy_overrides or {}

        # Handle relationships
        for rel_name, _rel_prop in self.relationships.items():
            # Skip if excluded
            if exclude_relationships and rel_name in exclude_relationships:
                options.append(noload(getattr(self.model_class, rel_name)))
                continue

            # Skip if not included (when include list is provided)
            if include_relationships and rel_name not in include_relationships:
                options.append(noload(getattr(self.model_class, rel_name)))
                continue

            # Apply strategy
            strategy = strategy_overrides.get(rel_name, LazyLoadingStrategy.LAZY)
            loader = LazyLoadingStrategy.get_loader(strategy)
            options.append(loader(getattr(self.model_class, rel_name)))

        # Handle deferred columns
        if defer_columns:
            for col in defer_columns:
                if col in self.columns:
                    options.append(defer(getattr(self.model_class, col)))

        return options

    def optimize_query(
        self,
        query: Query,
        needed_relationships: Optional[List[str]] = None,
        needed_columns: Optional[List[str]] = None,
    ) -> Query:
        """Optimize a query based on what data is needed.

        Args:
            query: Base query
            needed_relationships: Relationships that will be accessed
            needed_columns: Columns that will be accessed

        Returns:
            Optimized query
        """
        # Determine what to defer
        defer_columns = []
        if needed_columns:
            defer_columns = [
                col for col in self.columns if col not in needed_columns and col != "id"
            ]

        # Create loading options
        options = self.create_loading_options(
            include_relationships=needed_relationships,
            defer_columns=defer_columns,
        )

        # Apply options
        for option in options:
            query = query.options(option)

        return query


# Utility functions for common lazy loading patterns
def with_relationships(
    query: Query,
    model_class: Type[Any],
    *relationships: str,
    strategy: str = LazyLoadingStrategy.SELECTIN,
) -> Query:
    """Add relationship loading to a query.

    Args:
        query: Base query
        model_class: Model class
        relationships: Relationship names to load
        strategy: Loading strategy

    Returns:
        Query with relationship loading
    """
    loader = LazyLoadingStrategy.get_loader(strategy)

    for rel in relationships:
        if hasattr(model_class, rel):
            query = query.options(loader(getattr(model_class, rel)))
        else:
            logger.warning(f"Relationship {rel} not found on {model_class.__name__}")

    return query


def defer_expensive_columns(
    query: Query,
    model_class: Type[Any],
    columns: List[str],
) -> Query:
    """Defer loading of expensive columns.

    Args:
        query: Base query
        model_class: Model class
        columns: Column names to defer

    Returns:
        Query with deferred columns
    """
    for col in columns:
        if hasattr(model_class, col):
            query = query.options(defer(getattr(model_class, col)))
        else:
            logger.warning(f"Column {col} not found on {model_class.__name__}")

    return query


def create_optimized_query(
    session: Session,
    model_class: Type[Any],
    load_config: Dict[str, Any],
) -> Query:
    """Create an optimized query based on configuration.

    Args:
        session: Database session
        model_class: Model class to query
        load_config: Loading configuration

    Returns:
        Optimized query

    Example:
        config = {
            "relationships": {
                "user": "joined",
                "tags": "selectin",
            },
            "defer_columns": ["large_text_field", "binary_data"],
            "filters": {"is_active": True},
        }
        query = create_optimized_query(session, Post, config)
    """
    query = session.query(model_class)

    # Apply relationship loading
    relationships = load_config.get("relationships", {})
    for rel_name, strategy in relationships.items():
        if hasattr(model_class, rel_name):
            loader = LazyLoadingStrategy.get_loader(strategy)
            query = query.options(loader(getattr(model_class, rel_name)))

    # Defer columns
    defer_cols = load_config.get("defer_columns", [])
    for col in defer_cols:
        if hasattr(model_class, col):
            query = query.options(defer(getattr(model_class, col)))

    # Apply filters
    filters = load_config.get("filters", {})
    for attr_name, value in filters.items():
        if hasattr(model_class, attr_name):
            query = query.filter(getattr(model_class, attr_name) == value)

    return query


# Export components
__all__ = [
    "LazyLoadingStrategy",
    "LazyLoadingMixin",
    "lazy_property",
    "LazyLoader",
    "with_relationships",
    "defer_expensive_columns",
    "create_optimized_query",
]
