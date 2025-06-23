"""
Retrieval Pipeline Module for Haven Health Passport.

Provides comprehensive retrieval pipelines for document search and retrieval.
"""

from .base import (
    PipelineStage,
    QueryContext,
    RetrievalConfig,
    RetrievalPipeline,
    RetrievalResult,
)
from .factory import (
    RetrievalPipelineFactory,
    create_retrieval_pipeline,
    get_pipeline_for_use_case,
)
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
    MultilingualQueryProcessor,
    QueryExpander,
    QueryProcessor,
)
from .results import ResultAggregator, ResultExplainer, ResultFilter, ResultProcessor

__all__ = [
    # Base classes
    "RetrievalPipeline",
    "RetrievalConfig",
    "RetrievalResult",
    "QueryContext",
    "PipelineStage",
    # Query processing
    "QueryProcessor",
    "QueryExpander",
    "MedicalQueryExpander",
    "MultilingualQueryProcessor",
    # Pipelines
    "BasicRetrievalPipeline",
    "AdvancedRetrievalPipeline",
    "HybridRetrievalPipeline",
    "MultiStageRetrievalPipeline",
    "FederatedRetrievalPipeline",
    # Medical pipelines
    "MedicalRetrievalPipeline",
    "ClinicalRetrievalPipeline",
    "EmergencyRetrievalPipeline",
    "DrugInteractionPipeline",
    # Result processing
    "ResultProcessor",
    "ResultFilter",
    "ResultAggregator",
    "ResultExplainer",
    # Management
    "PipelineManager",
    "PipelineRouter",
    "PipelineMonitor",
    # Factory
    "RetrievalPipelineFactory",
    "create_retrieval_pipeline",
    "get_pipeline_for_use_case",
]
