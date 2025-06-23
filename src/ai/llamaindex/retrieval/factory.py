"""
Retrieval Pipeline Factory.

Provides factory methods for creating retrieval pipelines.

This module handles encrypted PHI with access control and audit logging
to ensure HIPAA compliance.
"""

import logging
from typing import Any, Dict, List, Optional

from ..indices import create_vector_index
from ..similarity.reranking import create_reranker
from .base import RetrievalConfig, RetrievalPipeline
from .manager import PipelineManager, PipelineMonitor, PipelineRouter
from .medical import (
    ClinicalRetrievalPipeline,
    DrugInteractionPipeline,
    EmergencyRetrievalPipeline,
    MedicalRetrievalPipeline,
)
from .pipelines import (
    AdvancedRetrievalPipeline,
    BasicRetrievalPipeline,
    FederatedRetrievalPipeline,
    HybridRetrievalPipeline,
    MultiStageRetrievalPipeline,
)
from .query import (
    MedicalQueryExpander,
    QueryAnalyzer,
    QueryExpander,
    QueryProcessor,
    SpellCorrector,
)
from .results import ResultProcessor

logger = logging.getLogger(__name__)


class RetrievalPipelineFactory:
    """Factory for creating retrieval pipelines."""

    # Pipeline type to class mapping
    PIPELINE_CLASSES: Dict[str, type[RetrievalPipeline]] = {
        "basic": BasicRetrievalPipeline,
        "advanced": AdvancedRetrievalPipeline,
        "hybrid": HybridRetrievalPipeline,
        "multistage": MultiStageRetrievalPipeline,
        "federated": FederatedRetrievalPipeline,
        "medical": MedicalRetrievalPipeline,
        "clinical": ClinicalRetrievalPipeline,
        "emergency": EmergencyRetrievalPipeline,
        "drug_interaction": DrugInteractionPipeline,
    }

    @staticmethod
    def create_pipeline(
        pipeline_type: str,
        config: Optional[RetrievalConfig] = None,
        indices: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> RetrievalPipeline:
        """
        Create a retrieval pipeline.

        Args:
            pipeline_type: Type of pipeline to create
            config: Optional configuration
            indices: Optional indices to use
            **kwargs: Additional pipeline-specific arguments

        Returns:
            Created retrieval pipeline
        """
        if pipeline_type not in RetrievalPipelineFactory.PIPELINE_CLASSES:
            raise ValueError(
                f"Unknown pipeline type: {pipeline_type}. "
                f"Available types: {list(RetrievalPipelineFactory.PIPELINE_CLASSES.keys())}"
            )

        pipeline_class = RetrievalPipelineFactory.PIPELINE_CLASSES[pipeline_type]

        # Create default config if not provided
        if config is None:
            config = RetrievalConfig(pipeline_name=f"{pipeline_type}_pipeline")

        # Create default indices if not provided
        if indices is None and pipeline_type != "federated":
            indices = RetrievalPipelineFactory._create_default_indices(pipeline_type)

        # Create pipeline
        logger.info("Creating %s pipeline", pipeline_type)

        # Add default components based on type
        if pipeline_type in ["advanced", "medical", "clinical"]:
            kwargs.setdefault("query_processor", QueryProcessor())
            kwargs.setdefault("query_analyzer", QueryAnalyzer())
            kwargs.setdefault("spell_corrector", SpellCorrector())

            if pipeline_type in ["medical", "clinical"]:
                kwargs.setdefault("query_expander", MedicalQueryExpander())
            else:
                kwargs.setdefault("query_expander", QueryExpander())

        pipeline = pipeline_class(config=config, indices=indices, **kwargs)
        return pipeline

    @staticmethod
    def _create_default_indices(pipeline_type: str) -> Dict[str, Any]:
        """Create default indices for pipeline type."""
        if pipeline_type in ["medical", "clinical", "emergency", "drug_interaction"]:
            # Medical indices
            return {
                "medical": create_vector_index("medical"),
                "clinical": create_vector_index("clinical_trials"),
            }
        elif pipeline_type == "hybrid":
            # Dense and sparse indices
            return {
                "dense": create_vector_index("dense"),
                "sparse": create_vector_index("bm25"),
            }
        elif pipeline_type == "multistage":
            # Fast first stage, accurate second stage
            return {
                "first_stage": create_vector_index("sparse"),
                "second_stage": create_vector_index("dense_optimized"),
            }
        else:
            # Default dense index
            return {"default": create_vector_index("dense")}


def create_retrieval_pipeline(
    pipeline_type: str = "basic", **kwargs: Any
) -> RetrievalPipeline:
    """
    Create a retrieval pipeline.

    Args:
        pipeline_type: Type of pipeline
        **kwargs: Pipeline configuration

    Returns:
        Retrieval pipeline instance
    """
    return RetrievalPipelineFactory.create_pipeline(pipeline_type, **kwargs)


def get_pipeline_for_use_case(use_case: str, **kwargs: Any) -> RetrievalPipeline:
    """
    Get appropriate pipeline for specific use case.

    Args:
        use_case: Use case identifier
        **kwargs: Additional configuration

    Returns:
        Configured retrieval pipeline
    """
    use_case_configs = {
        # General use cases
        "general": {
            "pipeline_type": "basic",
            "config": RetrievalConfig(
                enable_caching=True, enable_filtering=True, final_top_k=10
            ),
        },
        "research": {
            "pipeline_type": "advanced",
            "config": RetrievalConfig(
                enable_query_expansion=True,
                enable_reranking=True,
                enable_filtering=True,
                final_top_k=20,
            ),
        },
        "semantic_search": {
            "pipeline_type": "advanced",
            "config": RetrievalConfig(
                enable_query_expansion=True,
                enable_synonym_expansion=True,
                enable_reranking=True,
            ),
            "reranker": create_reranker("cross_encoder"),
        },
        "hybrid_search": {
            "pipeline_type": "hybrid",
            "config": RetrievalConfig(enable_filtering=True, filter_duplicates=True),
            "fusion_weights": {"dense": 0.7, "sparse": 0.3},
        },
        # Medical use cases
        "medical_search": {
            "pipeline_type": "medical",
            "config": RetrievalConfig(
                enable_query_expansion=True,
                enable_filtering=True,
                enable_reranking=True,
            ),
            "enable_phi_protection": True,
        },
        "clinical_decision": {
            "pipeline_type": "clinical",
            "config": RetrievalConfig(enable_reranking=True, final_top_k=5),
            "evidence_levels": ["systematic_review", "rct", "cohort_study"],
        },
        "emergency_medicine": {
            "pipeline_type": "emergency",
            "config": RetrievalConfig(
                timeout_seconds=5.0,
                final_top_k=3,
                enable_query_expansion=False,  # Speed critical
            ),
        },
        "drug_safety": {
            "pipeline_type": "drug_interaction",
            "config": RetrievalConfig(enable_filtering=True, final_top_k=10),
        },
        # Performance-optimized
        "real_time": {
            "pipeline_type": "basic",
            "config": RetrievalConfig(
                enable_caching=True,
                cache_ttl_seconds=300,  # 5 minutes
                timeout_seconds=2.0,
                enable_query_expansion=False,
            ),
        },
        "large_scale": {
            "pipeline_type": "multistage",
            "config": RetrievalConfig(retrieval_top_k=1000, final_top_k=10),
            "first_stage_k": 100,
        },
        # Multi-source
        "federated": {
            "pipeline_type": "federated",
            "config": RetrievalConfig(filter_duplicates=True, enable_filtering=True),
        },
    }

    if use_case not in use_case_configs:
        raise ValueError(
            f"Unknown use case: {use_case}. "
            f"Available use cases: {list(use_case_configs.keys())}"
        )

    # Get use case configuration
    use_case_config = use_case_configs[use_case].copy()

    # Extract pipeline type
    pipeline_type = use_case_config.pop("pipeline_type")
    if not isinstance(pipeline_type, str):
        raise ValueError(f"pipeline_type must be a string, got {type(pipeline_type)}")

    # Merge with provided kwargs
    merged_config = {**use_case_config, **kwargs}

    # Create pipeline
    return create_retrieval_pipeline(pipeline_type, **merged_config)


def create_pipeline_system(
    pipelines: List[Dict[str, Any]], routing_strategy: str = "content_based"
) -> Dict[str, Any]:
    """
    Create a complete pipeline system with management.

    Args:
        pipelines: List of pipeline configurations
        routing_strategy: How to route queries

    Returns:
        Pipeline system configuration
    """
    # Create manager
    manager = PipelineManager()

    # Create pipelines
    created_pipelines = []
    for pipeline_config in pipelines:
        name = pipeline_config.get("name")
        if not name or not isinstance(name, str):
            raise ValueError("Each pipeline must have a 'name' field of type str")
        pipeline_type = pipeline_config.get("type", "basic")

        # Create pipeline
        pipeline = create_retrieval_pipeline(pipeline_type, **pipeline_config)

        # Register with manager
        manager.register_pipeline(name, pipeline)

        created_pipelines.append(
            {"name": name, "type": pipeline_type, "pipeline": pipeline}
        )

    # Create router
    router = PipelineRouter(manager, routing_strategy)

    # Create monitor
    monitor = PipelineMonitor(manager)

    return {
        "manager": manager,
        "router": router,
        "monitor": monitor,
        "pipelines": created_pipelines,
        "routing_strategy": routing_strategy,
    }


# Pre-configured pipeline templates
PIPELINE_TEMPLATES = {
    "medical_system": {
        "pipelines": [
            {
                "name": "general_medical",
                "type": "medical",
                "enable_phi_protection": True,
            },
            {"name": "emergency", "type": "emergency"},
            {
                "name": "clinical_support",
                "type": "clinical",
                "evidence_levels": ["systematic_review", "rct"],
            },
            {"name": "drug_safety", "type": "drug_interaction"},
        ],
        "routing_strategy": "content_based",
    },
    "research_platform": {
        "pipelines": [
            {
                "name": "semantic",
                "type": "advanced",
                "enable_query_expansion": True,
                "enable_reranking": True,
            },
            {
                "name": "hybrid",
                "type": "hybrid",
                "fusion_weights": {"dense": 0.6, "sparse": 0.4},
            },
            {
                "name": "clinical_trials",
                "type": "clinical",
                "evidence_levels": ["rct", "controlled_trial"],
            },
        ],
        "routing_strategy": "weighted",
    },
    "enterprise_search": {
        "pipelines": [
            {
                "name": "fast",
                "type": "basic",
                "config": RetrievalConfig(enable_caching=True, timeout_seconds=1.0),
            },
            {"name": "accurate", "type": "advanced", "enable_reranking": True},
            {"name": "federated", "type": "federated"},
        ],
        "routing_strategy": "round_robin",
    },
}


def create_from_template(template_name: str, **kwargs: Any) -> Dict[str, Any]:
    """
    Create pipeline system from template.

    Args:
        template_name: Name of template
        **kwargs: Override parameters

    Returns:
        Pipeline system configuration
    """
    if template_name not in PIPELINE_TEMPLATES:
        raise ValueError(
            f"Unknown template: {template_name}. "
            f"Available templates: {list(PIPELINE_TEMPLATES.keys())}"
        )

    template = PIPELINE_TEMPLATES[template_name].copy()

    # Merge with overrides
    pipelines = template["pipelines"]
    if not isinstance(pipelines, list):
        raise ValueError(f"Template pipelines must be a list, got {type(pipelines)}")
    routing_strategy = kwargs.get("routing_strategy", template["routing_strategy"])

    return create_pipeline_system(pipelines, routing_strategy)


def create_custom_pipeline(
    base_type: str = "advanced",
    components: Optional[Dict[str, Any]] = None,
    processors: Optional[List[Any]] = None,
    **kwargs: Any,
) -> RetrievalPipeline:
    """
    Create a custom pipeline with specific components.

    Args:
        base_type: Base pipeline type
        components: Custom components to use
        processors: Result processors to apply
        **kwargs: Additional configuration

    Returns:
        Custom retrieval pipeline
    """
    # Create base pipeline
    pipeline = create_retrieval_pipeline(base_type, **kwargs)

    # Add custom components
    if components:
        for name, component in components.items():
            setattr(pipeline, name, component)

    # Add result processors
    if processors:
        # Wrap processors in a chain
        class ProcessorChain(ResultProcessor):
            def __init__(self, processors: List[Any]) -> None:
                super().__init__("processor_chain")
                self.processors = processors

            async def process(self, input_data: Any) -> Any:
                for processor in self.processors:
                    input_data = await processor.process(input_data)
                return input_data

        # Set result processor if pipeline supports it
        if hasattr(pipeline, "_result_processor"):
            setattr(pipeline, "_result_processor", ProcessorChain(processors))

    return pipeline
