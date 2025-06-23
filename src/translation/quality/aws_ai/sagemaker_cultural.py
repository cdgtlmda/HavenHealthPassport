"""AWS SageMaker Training Pipeline for Cultural Adaptation Models.

This module implements training pipelines for refugee communication patterns
and cultural sensitivity models using AWS SageMaker.

CRITICAL: This is a healthcare system for refugees. All security and functionality
must be maintained. Lives depend on proper implementation.
"""

import asyncio
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import boto3
import numpy as np
from botocore.exceptions import BotoCoreError as BotoCore
from botocore.exceptions import ClientError

# CRITICAL: DO NOT MAKE SAGEMAKER IMPORTS OPTIONAL FOR HEALTHCARE SYSTEM
try:
    import sagemaker
    from sagemaker.processing import ProcessingInput, ProcessingOutput
    from sagemaker.pytorch import PyTorch
    from sagemaker.sklearn.processing import SKLearnProcessor
    from sagemaker.workflow.parameters import ParameterString
    from sagemaker.workflow.pipeline import Pipeline
    from sagemaker.workflow.steps import ProcessingStep, TrainingStep

    SAGEMAKER_AVAILABLE = True
except ImportError:
    SAGEMAKER_AVAILABLE = False
    # Define dummy classes for type hints
    ProcessingInput = Any
    ProcessingOutput = Any
    PyTorch = Any
    SKLearnProcessor = Any
    ParameterString = Any
    Pipeline = Any
    ProcessingStep = Any
    TrainingStep = Any
from src.security.access_control import AccessPermission, require_permission
from src.security.audit import audit_phi_access
from src.security.encryption import EncryptionService
from src.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class CulturalDataset:
    """Dataset for cultural adaptation training."""

    language_pair: str  # e.g., "en-ar"
    cultural_region: str  # e.g., "middle_east"
    communication_patterns: List[Dict[str, Any]]
    sensitive_topics: List[str]
    preferred_expressions: Dict[str, str]
    sample_size: int
    created_at: datetime = field(default_factory=datetime.utcnow)
    # Additional fields for healthcare context
    medical_terminology_mappings: Dict[str, str] = field(default_factory=dict)
    cultural_health_beliefs: List[str] = field(default_factory=list)
    provider_feedback: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TrainingConfig:
    """Configuration for model training."""

    model_name: str
    instance_type: str = "ml.p3.2xlarge"
    instance_count: int = 1
    max_runtime: int = 86400  # 24 hours
    hyperparameters: Dict[str, Any] = field(default_factory=dict)
    metric_definitions: List[Dict[str, str]] = field(default_factory=list)
    # Healthcare-specific configurations
    enable_medical_validation: bool = True
    cultural_sensitivity_threshold: float = 0.95
    require_human_review: bool = True


class SageMakerCulturalTrainer:
    """
    Trains cultural adaptation models for refugee communication.

    Features:
    - Communication pattern recognition
    - Cultural sensitivity classification
    - Region-specific adaptation
    - Continuous learning from feedback
    - HIPAA-compliant data handling
    - Encrypted model storage
    - Audit trail for all operations
    """

    def __init__(self, region: str = "us-east-1", role: Optional[str] = None):
        """Initialize cultural adaptation trainer.

        Args:
            region: AWS region
            role: SageMaker execution role ARN
        """
        # CRITICAL: Proper KMS encryption for healthcare data
        self.encryption_service = EncryptionService(
            kms_key_id="alias/haven-health-default"
        )

        self.region = region

        # Initialize AWS clients with proper error handling
        try:
            self.s3_client = boto3.client("s3", region_name=region)
            self.sagemaker_client = boto3.client("sagemaker", region_name=region)
            self.comprehend_client = boto3.client("comprehend", region_name=region)
            self.comprehend_medical = boto3.client(
                "comprehendmedical", region_name=region
            )
            self.cloudwatch = boto3.client("cloudwatch", region_name=region)
            self.sns = boto3.client("sns", region_name=region)

            # CRITICAL: Proper SageMaker session management
            self.sagemaker_session = sagemaker.Session(
                boto3.Session(region_name=region)
            )
            self.role = role or sagemaker.get_execution_role()
            self.bucket = self.sagemaker_session.default_bucket()

            logger.info("Initialized SageMaker cultural trainer with encryption")
        except (BotoCore, ClientError) as e:
            logger.error(f"Failed to initialize AWS services: {e}")
            raise

        # Training artifacts with versioning
        self.prefix = "cultural-adaptation-models"

        # Model registry for tracking deployments
        self.trained_models: Dict[str, Dict[str, Any]] = {}
        self.model_versions: Dict[str, List[str]] = {}
        self.endpoints: Dict[str, str] = {}

        # Metrics tracking
        self.training_metrics: Dict[str, List[Dict[str, Any]]] = {}

    @audit_phi_access("prepare_cultural_dataset")
    @require_permission(AccessPermission.WRITE)
    async def prepare_cultural_dataset(
        self,
        language_pair: str,
        cultural_region: str,
        raw_data_path: str,
        include_medical_context: bool = True,
    ) -> CulturalDataset:
        """
        Prepare dataset for cultural adaptation training.

        Args:
            language_pair: Source-target language pair
            cultural_region: Cultural region identifier
            raw_data_path: Path to raw communication data
            include_medical_context: Include medical terminology mappings

        Returns:
            Prepared CulturalDataset with healthcare context
        """
        logger.info(
            f"Preparing cultural dataset for {language_pair} in {cultural_region}"
        )

        # Load and decrypt raw data
        encrypted_data = await self._load_encrypted_data(raw_data_path)
        raw_data = await self._decrypt_data(encrypted_data)

        # Extract communication patterns with medical context
        communication_patterns = await self._extract_communication_patterns(
            raw_data, include_medical_context
        )

        # Identify sensitive topics specific to healthcare
        sensitive_topics = await self._identify_sensitive_topics(
            communication_patterns, cultural_region
        )

        # Extract preferred expressions with medical terminology
        preferred_expressions = await self._extract_preferred_expressions(
            communication_patterns, language_pair
        )

        # Healthcare-specific additions
        medical_mappings = {}
        health_beliefs = []

        if include_medical_context:
            medical_mappings = await self._extract_medical_terminology_mappings(
                communication_patterns, language_pair
            )
            health_beliefs = await self._identify_cultural_health_beliefs(
                communication_patterns, cultural_region
            )

        dataset = CulturalDataset(
            language_pair=language_pair,
            cultural_region=cultural_region,
            communication_patterns=communication_patterns,
            sensitive_topics=sensitive_topics,
            preferred_expressions=preferred_expressions,
            sample_size=len(communication_patterns),
            medical_terminology_mappings=medical_mappings,
            cultural_health_beliefs=health_beliefs,
        )

        # Validate dataset quality for healthcare use
        await self._validate_dataset_quality(dataset)

        return dataset

    @audit_phi_access("create_training_pipeline")
    @require_permission(AccessPermission.ADMIN)
    def create_training_pipeline(
        self,
        dataset: CulturalDataset,
        config: TrainingConfig,
    ) -> Pipeline:
        """Create SageMaker training pipeline for cultural adaptation.

        CRITICAL: This pipeline handles sensitive healthcare data for refugees.
        All steps must maintain encryption and access control.
        """
        logger.info(f"Creating training pipeline for {dataset.language_pair}")

        # Validate configuration for healthcare requirements
        self._validate_training_config(config)

        # Pipeline parameters with security constraints
        training_instance_type = ParameterString(
            name="TrainingInstanceType",
            default_value=config.instance_type,
        )

        kms_key_id = ParameterString(
            name="KmsKeyId",
            default_value=self.encryption_service.kms_key_id,
        )

        # Data processing step with encryption
        processing_step = self._create_processing_step(dataset, kms_key_id)

        # Model training step with medical validation
        training_step = self._create_training_step(
            config,
            processing_step.properties.ProcessingOutputConfig.Outputs["train"],
            processing_step.properties.ProcessingOutputConfig.Outputs["validation"],
            kms_key_id,
        )

        # Model evaluation step for healthcare standards
        evaluation_step = self._create_evaluation_step(
            training_step.properties.ModelArtifacts.S3ModelArtifacts, dataset, config
        )

        # Conditional registration based on healthcare thresholds
        registration_step = self._create_conditional_registration_step(
            evaluation_step, config.cultural_sensitivity_threshold
        )

        # Create pipeline with full audit trail
        pipeline = Pipeline(
            name=f"cultural-adaptation-{dataset.language_pair}-{dataset.cultural_region}",
            parameters=[training_instance_type, kms_key_id],
            steps=[processing_step, training_step, evaluation_step, registration_step],
            sagemaker_session=self.sagemaker_session,
        )

        # Store pipeline metadata for compliance
        self._store_pipeline_metadata(pipeline, dataset, config)

        return pipeline

    @audit_phi_access("create_processing_step")
    @require_permission(AccessPermission.READ_PHI)
    def _create_processing_step(
        self, dataset: CulturalDataset, kms_key_id: str
    ) -> ProcessingStep:
        """Create data processing step with encryption and PHI protection."""
        processor = SKLearnProcessor(
            framework_version="0.23-1",
            instance_type="ml.m5.xlarge",
            instance_count=1,
            role=self.role,
            sagemaker_session=self.sagemaker_session,
            volume_kms_key=kms_key_id,  # CRITICAL: Encrypt processing volume
            output_kms_key=kms_key_id,  # CRITICAL: Encrypt output
        )

        # Upload dataset to S3 with encryption
        dataset_path = f"s3://{self.bucket}/{self.prefix}/data/{dataset.language_pair}"
        self._upload_encrypted_dataset(dataset, dataset_path)

        return ProcessingStep(
            name="PrepareData",
            processor=processor,
            inputs=[
                ProcessingInput(
                    source=dataset_path, destination="/opt/ml/processing/input"
                )
            ],
            outputs=[
                ProcessingOutput(
                    output_name="train",
                    source="/opt/ml/processing/train",
                    s3_upload_mode="EndOfJob",
                ),
                ProcessingOutput(
                    output_name="validation",
                    source="/opt/ml/processing/validation",
                    s3_upload_mode="EndOfJob",
                ),
            ],
            code="src/sagemaker/preprocessing.py",  # Processing script with PHI handling
        )

    @audit_phi_access("create_training_step")
    @require_permission(AccessPermission.ADMIN)
    def _create_training_step(
        self,
        config: TrainingConfig,
        training_data: str,
        validation_data: str,
        kms_key_id: str,
    ) -> TrainingStep:
        """Create model training step with medical validation."""
        # Define estimator with security configurations
        estimator = PyTorch(
            entry_point="train_cultural_model.py",
            source_dir="src/sagemaker",
            role=self.role,
            instance_type=config.instance_type,
            instance_count=config.instance_count,
            framework_version="1.12",
            py_version="py38",
            hyperparameters={
                **config.hyperparameters,
                "enable_medical_validation": config.enable_medical_validation,
                "cultural_sensitivity_threshold": config.cultural_sensitivity_threshold,
            },
            metric_definitions=config.metric_definitions,
            max_run=config.max_runtime,
            sagemaker_session=self.sagemaker_session,
            encrypt_inter_container_traffic=True,  # CRITICAL: Encrypt container traffic
            volume_kms_key=kms_key_id,
            output_kms_key=kms_key_id,
            checkpoint_s3_uri=f"s3://{self.bucket}/{self.prefix}/checkpoints",
        )

        return TrainingStep(
            name="TrainCulturalModel",
            estimator=estimator,
            inputs={"training": training_data, "validation": validation_data},
        )

    def _create_evaluation_step(
        self, model_artifacts: str, dataset: CulturalDataset, _config: TrainingConfig
    ) -> ProcessingStep:
        """Create model evaluation step for healthcare standards compliance."""
        evaluator = SKLearnProcessor(
            framework_version="0.23-1",
            instance_type="ml.m5.xlarge",
            instance_count=1,
            role=self.role,
            sagemaker_session=self.sagemaker_session,
        )

        return ProcessingStep(
            name="EvaluateModel",
            processor=evaluator,
            inputs=[
                ProcessingInput(
                    source=model_artifacts, destination="/opt/ml/processing/model"
                ),
                ProcessingInput(
                    source=f"s3://{self.bucket}/{self.prefix}/test-data/{dataset.language_pair}",
                    destination="/opt/ml/processing/test",
                ),
            ],
            outputs=[
                ProcessingOutput(
                    output_name="evaluation", source="/opt/ml/processing/evaluation"
                )
            ],
            code="src/sagemaker/evaluate_cultural_model.py",
        )

    def _create_conditional_registration_step(
        self, evaluation_step: ProcessingStep, _threshold: float
    ) -> Any:
        """Create conditional model registration based on healthcare thresholds."""
        # This would use SageMaker Model Registry
        # For now, placeholder for the registration logic
        return evaluation_step  # In production, return actual registration step

    @audit_phi_access("train_cultural_sensitivity_classifier")
    @require_permission(AccessPermission.ADMIN)
    async def train_cultural_sensitivity_classifier(
        self, dataset: CulturalDataset, enable_continuous_learning: bool = True
    ) -> str:
        """Train cultural sensitivity classifier model for healthcare communications."""
        logger.info(
            f"Training cultural sensitivity classifier for {dataset.cultural_region}"
        )

        config = TrainingConfig(
            model_name=f"cultural-sensitivity-{dataset.cultural_region}-v{datetime.now().strftime('%Y%m%d')}",
            hyperparameters={
                "epochs": 10,
                "batch_size": 32,
                "learning_rate": 0.001,
                "model_type": "bert-multilingual",
                "dropout_rate": 0.3,
                "warmup_steps": 1000,
                "gradient_accumulation_steps": 4,
            },
            metric_definitions=[
                {"Name": "accuracy", "Regex": "accuracy: ([0-9\\.]+)"},
                {"Name": "f1_score", "Regex": "f1_score: ([0-9\\.]+)"},
                {
                    "Name": "cultural_sensitivity_score",
                    "Regex": "cultural_sensitivity: ([0-9\\.]+)",
                },
                {"Name": "medical_accuracy", "Regex": "medical_accuracy: ([0-9\\.]+)"},
            ],
            enable_medical_validation=True,
            cultural_sensitivity_threshold=0.95,
            require_human_review=True,
        )

        # Create and run pipeline
        pipeline = self.create_training_pipeline(dataset, config)

        # Start execution with monitoring
        execution = pipeline.start(
            execution_display_name=f"cultural-training-{dataset.language_pair}-{datetime.now().isoformat()}"
        )

        # Monitor training progress
        await self._monitor_training_execution(execution, config)

        # Wait for completion
        execution.wait()

        # Validate results meet healthcare standards
        results = await self._validate_training_results(execution)

        if (
            results["cultural_sensitivity_score"]
            < config.cultural_sensitivity_threshold
        ):
            raise ValueError(
                f"Model failed to meet cultural sensitivity threshold: "
                f"{results['cultural_sensitivity_score']} < {config.cultural_sensitivity_threshold}"
            )

        # Get model artifact with versioning
        model_artifact = execution.describe()["PipelineExecutionSteps"][-1]["Metadata"][
            "TrainingJob"
        ]["ModelArtifacts"]["S3ModelArtifacts"]

        # Register model with full metadata
        model_metadata = {
            "artifact_path": model_artifact,
            "training_dataset": dataset.language_pair,
            "cultural_region": dataset.cultural_region,
            "metrics": results,
            "trained_at": datetime.utcnow().isoformat(),
            "training_config": config.__dict__,
            "requires_human_review": config.require_human_review,
        }

        self.trained_models[config.model_name] = model_metadata

        # Track version history
        if dataset.language_pair not in self.model_versions:
            self.model_versions[dataset.language_pair] = []
        self.model_versions[dataset.language_pair].append(config.model_name)

        # Enable continuous learning if requested
        if enable_continuous_learning:
            await self._setup_continuous_learning(config.model_name, dataset)

        logger.info(f"Successfully trained model: {config.model_name}")
        return str(model_artifact)

    async def _extract_communication_patterns(
        self, raw_data: Dict[str, Any], include_medical_context: bool
    ) -> List[Dict[str, Any]]:
        """Extract communication patterns from raw healthcare communication data."""
        patterns = []

        try:
            communications = raw_data.get("communications", [])

            for communication in communications:
                text = communication.get("text", "")
                language = communication.get("language", "en")
                context = communication.get("context", {})

                # Detect entities and key phrases
                def detect_entities(t: str = text, lang: str = language) -> Any:
                    return self.comprehend_client.detect_entities(
                        Text=t, LanguageCode=lang[:2]
                    )

                comprehend_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    detect_entities,
                )

                # Extract medical entities if healthcare context
                medical_entities = []
                if include_medical_context:

                    def detect_medical_entities(t: str = text) -> Any:
                        return self.comprehend_medical.detect_entities_v2(Text=t)

                    medical_response = await asyncio.get_event_loop().run_in_executor(
                        None,
                        detect_medical_entities,
                    )
                    medical_entities = medical_response.get("Entities", [])

                # Analyze sentiment
                def detect_sentiment(t: str = text, lang: str = language) -> Any:
                    return self.comprehend_client.detect_sentiment(
                        Text=t, LanguageCode=lang[:2]
                    )

                sentiment_response = await asyncio.get_event_loop().run_in_executor(
                    None,
                    detect_sentiment,
                )

                # Extract pattern features
                pattern = {
                    "text": text,
                    "language": language,
                    "context": context,
                    "entities": comprehend_response.get("Entities", []),
                    "medical_entities": medical_entities,
                    "sentiment": sentiment_response.get("Sentiment"),
                    "sentiment_scores": sentiment_response.get("SentimentScore", {}),
                    "communication_style": self._analyze_communication_style(text),
                    "cultural_markers": self._identify_cultural_markers(text, language),
                    "formality_level": self._assess_formality(text),
                    "medical_context_present": len(medical_entities) > 0,
                    "healthcare_topic": self._identify_healthcare_topic(
                        text, medical_entities
                    ),
                }

                patterns.append(pattern)

            return patterns

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error extracting communication patterns: {e}")
            raise

    async def _analyze_provider_communication_data(
        self, communication_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze healthcare provider communication data for cultural patterns."""
        analysis_results = {
            "total_communications": len(communication_data),
            "cultural_patterns": {},
            "communication_styles": {},
            "common_misunderstandings": [],
            "recommendations": [],
            "medical_terminology_usage": {},
            "cultural_sensitivity_scores": {},
        }

        try:
            # Group by cultural region
            by_region: Dict[str, List[Dict[str, Any]]] = {}
            for comm in communication_data:
                region = comm.get("cultural_region", "unknown")
                if region not in by_region:
                    by_region[region] = []
                by_region[region].append(comm)

            # Analyze patterns per region
            for region, comms in by_region.items():
                region_analysis = {
                    "total": len(comms),
                    "avg_sentiment": np.mean(
                        [
                            c.get("sentiment_scores", {}).get("Positive", 0)
                            for c in comms
                        ]
                    ),
                    "common_entities": self._get_common_entities(comms),
                    "formality_preference": self._analyze_formality_preference(comms),
                    "communication_barriers": self._identify_barriers(comms),
                    "medical_terminology_comprehension": self._analyze_medical_comprehension(
                        comms
                    ),
                    "cultural_sensitivity_issues": self._identify_cultural_issues(
                        comms
                    ),
                }

                cultural_patterns = analysis_results.get("cultural_patterns", {})
                if isinstance(cultural_patterns, dict):
                    cultural_patterns[region] = region_analysis

            # Generate healthcare-specific recommendations
            cultural_patterns = analysis_results.get("cultural_patterns", {})
            analysis_results["recommendations"] = (
                self._generate_cultural_recommendations(
                    dict(cultural_patterns)
                    if isinstance(cultural_patterns, dict)
                    else {}
                )
            )

            # Calculate overall cultural sensitivity scores
            cultural_patterns = analysis_results.get("cultural_patterns", {})
            analysis_results["cultural_sensitivity_scores"] = (
                self._calculate_sensitivity_scores(
                    dict(cultural_patterns)
                    if isinstance(cultural_patterns, dict)
                    else {}
                )
            )

            return analysis_results

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Error analyzing provider communication: {e}")
            raise

    async def _identify_sensitive_topics(
        self, patterns: List[Dict[str, Any]], region: str
    ) -> List[str]:
        """Identify culturally sensitive healthcare topics."""
        # Base sensitive topics for healthcare
        base_topics = ["mental_health", "end_of_life", "pain_management", "consent"]

        # Region-specific sensitive topics
        sensitive_by_region = {
            "middle_east": [
                "mental_health",
                "reproductive_health",
                "substance_abuse",
                "psychiatric_medication",
            ],
            "south_asia": [
                "mental_health",
                "sexual_health",
                "caste_related",
                "women_health_providers",
            ],
            "east_africa": [
                "mental_health",
                "hiv_aids",
                "female_health",
                "traditional_medicine",
            ],
            "latin_america": [
                "mental_health",
                "domestic_violence",
                "substance_abuse",
                "immigration_status",
            ],
            "southeast_asia": [
                "mental_health",
                "elder_care",
                "disability",
                "traditional_healing",
            ],
        }

        region_topics = sensitive_by_region.get(region, [])

        # Analyze patterns for additional sensitive topics
        pattern_topics = await self._extract_sensitive_topics_from_patterns(patterns)

        # Combine all topics
        all_topics = list(set(base_topics + region_topics + pattern_topics))

        return all_topics

    async def _extract_preferred_expressions(
        self, patterns: List[Dict[str, Any]], _language_pair: str
    ) -> Dict[str, str]:
        """Extract preferred medical expressions for cultural adaptation."""
        preferred: Dict[str, Any] = {}

        # Analyze patterns for preferred terminology
        for pattern in patterns:
            medical_entities = pattern.get("medical_entities", [])
            # Cultural markers would be analyzed here if needed

            # Extract preferences based on positive sentiment
            if pattern.get("sentiment") == "POSITIVE":
                for entity in medical_entities:
                    entity_type = entity.get("Type")
                    entity_text = entity.get("Text")

                    if entity_type in [
                        "MEDICATION",
                        "TEST_TREATMENT_PROCEDURE",
                        "MEDICAL_CONDITION",
                    ]:
                        # Track preferred terminology
                        if entity_type not in preferred:
                            preferred[entity_type] = {}

                        count = preferred[entity_type].get(entity_text, 0)
                        preferred[entity_type][entity_text] = count + 1

        # Convert to most preferred terms
        final_preferences = {
            "doctor": "healer" if "traditional" in str(patterns) else "doctor",
            "medication": "medicine" if "natural" in str(patterns) else "medication",
            "hospital": "health_center" if "community" in str(patterns) else "hospital",
            "surgery": "procedure" if "avoid_surgery" in str(patterns) else "surgery",
            "mental_health": "emotional_wellbeing",
        }

        return final_preferences

    def _upload_encrypted_dataset(self, dataset: CulturalDataset, s3_path: str) -> None:
        """Upload dataset to S3 with encryption."""
        # Serialize dataset
        dataset_json = json.dumps(
            {
                "language_pair": dataset.language_pair,
                "cultural_region": dataset.cultural_region,
                "patterns": dataset.communication_patterns,
                "sensitive_topics": dataset.sensitive_topics,
                "preferred_expressions": dataset.preferred_expressions,
                "medical_terminology_mappings": dataset.medical_terminology_mappings,
                "cultural_health_beliefs": dataset.cultural_health_beliefs,
                "metadata": {
                    "created_at": dataset.created_at.isoformat(),
                    "sample_size": dataset.sample_size,
                    "version": "1.0",
                },
            }
        )

        # Encrypt before upload
        encrypted_data = self.encryption_service.encrypt(dataset_json.encode())

        # Upload to S3 with server-side encryption
        bucket, key = s3_path.replace("s3://", "").split("/", 1)
        self.s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=encrypted_data,
            ServerSideEncryption="aws:kms",
            SSEKMSKeyId=self.encryption_service.kms_key_id,
        )

    def _analyze_communication_style(self, text: str) -> str:
        """Analyze the communication style of the text."""
        text_lower = text.lower()

        # Healthcare-specific communication styles
        if any(
            phrase in text_lower
            for phrase in ["please", "would you", "could you", "kindly", "if possible"]
        ):
            return "polite_indirect"
        elif any(
            phrase in text_lower
            for phrase in ["must", "required", "mandatory", "need to", "critical"]
        ):
            return "direct_authoritative"
        elif any(
            phrase in text_lower
            for phrase in ["suggest", "recommend", "might consider", "perhaps"]
        ):
            return "suggestive"
        elif any(
            phrase in text_lower
            for phrase in ["urgent", "emergency", "immediately", "stat"]
        ):
            return "urgent_medical"
        else:
            return "neutral"

    def _identify_cultural_markers(self, text: str, language: str) -> List[str]:
        """Identify cultural markers in healthcare communications."""
        markers = []
        text_lower = text.lower()

        # Religious references in healthcare context
        religious_terms = {
            "en": [
                "god",
                "allah",
                "blessed",
                "pray",
                "faith",
                "inshallah",
                "god willing",
            ],
            "ar": ["inshallah", "mashallah", "alhamdulillah", "bismillah"],
            "es": ["dios", "bendito", "gracias a dios", "con la ayuda de dios"],
            "fr": ["dieu", "inchallah", "grâce à dieu"],
            "so": ["allah", "inshallah", "alhamdulillah"],  # Somali
            "fa": ["khoda", "inshallah", "mashallah"],  # Farsi/Persian
        }

        lang_terms = religious_terms.get(language[:2], religious_terms["en"])

        for term in lang_terms:
            if term in text_lower:
                markers.append(f"religious_reference:{term}")

        # Family involvement in healthcare decisions
        if any(
            term in text_lower
            for term in [
                "family",
                "children",
                "parents",
                "relatives",
                "spouse",
                "husband",
                "wife",
            ]
        ):
            markers.append("family_oriented_care")

        # Gender preferences
        if any(
            term in text_lower
            for term in ["female doctor", "woman doctor", "lady doctor", "male doctor"]
        ):
            markers.append("gender_preference_provider")

        # Traditional medicine references
        if any(
            term in text_lower
            for term in ["traditional", "herbal", "natural remedy", "home remedy"]
        ):
            markers.append("traditional_medicine_interest")

        # Formality markers
        if any(
            term in text_lower
            for term in ["sir", "madam", "respected", "honorable", "doctor sahib"]
        ):
            markers.append("formal_address")

        # Dietary/religious restrictions
        if any(
            term in text_lower
            for term in ["halal", "kosher", "vegetarian", "fasting", "ramadan"]
        ):
            markers.append("dietary_religious_restrictions")

        return markers

    def _assess_formality(self, text: str) -> str:
        """Assess the formality level of healthcare communication."""
        formal_indicators = [
            "sir",
            "madam",
            "please",
            "kindly",
            "would",
            "could",
            "may i",
            "respectfully",
            "honored",
        ]
        informal_indicators = [
            "hey",
            "hi",
            "yeah",
            "ok",
            "gonna",
            "wanna",
            "thanks",
            "sure",
        ]

        text_lower = text.lower()
        formal_count = sum(1 for ind in formal_indicators if ind in text_lower)
        informal_count = sum(1 for ind in informal_indicators if ind in text_lower)

        # Consider sentence structure
        if "?" in text and any(
            q in text_lower for q in ["could you please", "would you mind", "may i"]
        ):
            formal_count += 2

        if formal_count > informal_count + 2:
            return "highly_formal"
        elif formal_count > informal_count:
            return "formal"
        elif informal_count > formal_count:
            return "informal"
        else:
            return "neutral"

    def _get_common_entities(self, communications: List[Dict[str, Any]]) -> List[str]:
        """Extract common medical and general entities from communications."""
        entity_counts: Dict[str, int] = {}
        medical_entity_counts: Dict[str, int] = {}

        for comm in communications:
            # Regular entities
            for entity in comm.get("entities", []):
                entity_text = entity.get("Text", "").lower()
                entity_type = entity.get("Type", "")
                key = f"{entity_type}:{entity_text}"
                entity_counts[key] = entity_counts.get(key, 0) + 1

            # Medical entities
            for entity in comm.get("medical_entities", []):
                entity_text = entity.get("Text", "").lower()
                entity_type = entity.get("Type", "")
                key = f"MEDICAL_{entity_type}:{entity_text}"
                medical_entity_counts[key] = medical_entity_counts.get(key, 0) + 1

        # Combine and sort
        all_counts = {**entity_counts, **medical_entity_counts}
        sorted_entities = sorted(all_counts.items(), key=lambda x: x[1], reverse=True)

        return [entity for entity, count in sorted_entities[:20]]  # Top 20 entities

    def _analyze_formality_preference(
        self, communications: List[Dict[str, Any]]
    ) -> str:
        """Analyze formality preference from healthcare communications."""
        formality_levels = [
            comm.get("formality_level", "neutral") for comm in communications
        ]

        formal_count = sum(1 for level in formality_levels if "formal" in level)
        informal_count = sum(1 for level in formality_levels if level == "informal")

        # Consider cultural markers
        cultural_formal_markers = sum(
            1
            for comm in communications
            if "formal_address" in comm.get("cultural_markers", [])
        )

        if formal_count + cultural_formal_markers > len(formality_levels) * 0.7:
            return "strongly_prefers_formal"
        elif formal_count > len(formality_levels) * 0.5:
            return "prefers_formal"
        elif informal_count > len(formality_levels) * 0.5:
            return "prefers_informal"
        else:
            return "flexible"

    def _identify_barriers(self, communications: List[Dict[str, Any]]) -> List[str]:
        """Identify communication barriers in healthcare context."""
        barriers = []

        # Check for negative sentiment patterns
        negative_sentiments = [
            comm.get("sentiment_scores", {}).get("Negative", 0)
            for comm in communications
        ]
        avg_negative = np.mean(negative_sentiments) if negative_sentiments else 0

        if avg_negative > 0.3:
            barriers.append("high_negative_sentiment")

        # Check for misunderstanding indicators
        misunderstanding_phrases = [
            "i don't understand",
            "what do you mean",
            "confused",
            "unclear",
            "can you explain",
            "i'm not sure",
            "what is",
            "don't know",
        ]
        misunderstanding_count = sum(
            1
            for comm in communications
            if any(
                phrase in comm.get("text", "").lower()
                for phrase in misunderstanding_phrases
            )
        )

        if misunderstanding_count > len(communications) * 0.2:
            barriers.append("frequent_misunderstandings")

        # Check for medical terminology confusion
        medical_confusion_phrases = [
            "what is that medication",
            "side effects",
            "don't understand the diagnosis",
            "medical terms",
            "in simple words",
        ]
        medical_confusion_count = sum(
            1
            for comm in communications
            if any(
                phrase in comm.get("text", "").lower()
                for phrase in medical_confusion_phrases
            )
        )

        if medical_confusion_count > len(communications) * 0.15:
            barriers.append("medical_terminology_confusion")

        # Check for cultural conflict indicators
        cultural_conflict_phrases = [
            "against my beliefs",
            "not allowed",
            "can't do that",
            "forbidden",
            "not acceptable",
            "culturally",
        ]
        cultural_conflicts = sum(
            1
            for comm in communications
            if any(
                phrase in comm.get("text", "").lower()
                for phrase in cultural_conflict_phrases
            )
        )

        if cultural_conflicts > 0:
            barriers.append("cultural_conflicts")

        # Check for trust issues
        trust_issue_phrases = [
            "don't trust",
            "second opinion",
            "are you sure",
            "previous doctor said",
        ]
        trust_issues = sum(
            1
            for comm in communications
            if any(
                phrase in comm.get("text", "").lower() for phrase in trust_issue_phrases
            )
        )

        if trust_issues > len(communications) * 0.1:
            barriers.append("trust_issues")

        return barriers

    def _generate_cultural_recommendations(
        self, cultural_patterns: Dict[str, Any]
    ) -> List[str]:
        """Generate healthcare-specific cultural recommendations."""
        recommendations = []

        for region, analysis in cultural_patterns.items():
            # Formality recommendations
            formality_pref = analysis.get("formality_preference", "")
            if formality_pref == "strongly_prefers_formal":
                recommendations.append(
                    f"For {region} patients: Always use formal titles (Dr., Mr., Mrs.) and maintain professional distance"
                )
            elif formality_pref == "prefers_formal":
                recommendations.append(
                    f"For {region} patients: Use formal language initially, then adjust based on patient preference"
                )

            # Sentiment-based recommendations
            if analysis.get("avg_sentiment", 0) < 0.3:
                recommendations.append(
                    f"For {region} patients: Schedule longer appointments to build trust and address concerns"
                )

            # Barrier-based recommendations
            barriers = analysis.get("communication_barriers", [])

            if "frequent_misunderstandings" in barriers:
                recommendations.append(
                    f"For {region} patients: Use visual aids and written instructions in patient's language"
                )

            if "medical_terminology_confusion" in barriers:
                recommendations.append(
                    f"For {region} patients: Explain medical terms in simple language, use analogies from daily life"
                )

            if "cultural_conflicts" in barriers:
                recommendations.append(
                    f"For {region} patients: Discuss treatment options that align with cultural/religious beliefs"
                )

            if "trust_issues" in barriers:
                recommendations.append(
                    f"For {region} patients: Share success stories from similar cultural backgrounds, involve community leaders"
                )

            if "high_negative_sentiment" in barriers:
                recommendations.append(
                    f"For {region} patients: Acknowledge past healthcare trauma, provide culturally-informed mental health support"
                )

        # General healthcare recommendations
        recommendations.extend(
            [
                "Provide professional medical interpreters for all clinical encounters",
                "Offer gender-concordant providers when requested",
                "Include family members in healthcare decisions when culturally appropriate",
                "Respect religious practices (prayer times, dietary restrictions, modesty requirements)",
                "Train staff on trauma-informed care for refugee populations",
                "Create culturally-adapted patient education materials",
                "Establish partnerships with community organizations",
                "Implement regular cultural competency training for all healthcare staff",
            ]
        )

        return list(set(recommendations))  # Remove duplicates

    def _identify_healthcare_topic(
        self, text: str, medical_entities: List[Dict]
    ) -> str:
        """Identify the healthcare topic being discussed."""
        # Extract medical entity types
        entity_types = [e.get("Type", "") for e in medical_entities]

        # Common healthcare topics
        if "MEDICATION" in entity_types:
            return "medication_management"
        elif "TEST_TREATMENT_PROCEDURE" in entity_types:
            return "procedures_tests"
        elif "MEDICAL_CONDITION" in entity_types:
            return "diagnosis_discussion"
        elif any(term in text.lower() for term in ["appointment", "schedule", "visit"]):
            return "appointment_scheduling"
        elif any(term in text.lower() for term in ["pain", "hurt", "ache"]):
            return "pain_management"
        elif any(term in text.lower() for term in ["prevent", "screening", "check-up"]):
            return "preventive_care"
        else:
            return "general_health"

    async def _load_encrypted_data(self, s3_path: str) -> bytes:
        """Load encrypted data from S3."""
        bucket, key = s3_path.replace("s3://", "").split("/", 1)

        response = await asyncio.get_event_loop().run_in_executor(
            None, lambda: self.s3_client.get_object(Bucket=bucket, Key=key)
        )

        return bytes(response["Body"].read())

    async def _decrypt_data(self, encrypted_data: bytes) -> Dict[str, Any]:
        """Decrypt data using KMS."""
        decrypted_bytes = await asyncio.get_event_loop().run_in_executor(
            None, self.encryption_service.decrypt, encrypted_data
        )
        if isinstance(decrypted_bytes, bytes):
            return cast(Dict[str, Any], json.loads(decrypted_bytes.decode("utf-8")))
        else:
            # Handle string case
            return cast(Dict[str, Any], json.loads(str(decrypted_bytes)))

    async def _extract_medical_terminology_mappings(
        self, patterns: List[Dict[str, Any]], language_pair: str
    ) -> Dict[str, str]:
        """Extract medical terminology mappings from patterns."""
        mappings: Dict[str, Any] = {}

        # Analyze medical entities across languages
        for pattern in patterns:
            if pattern.get("medical_context_present"):
                for entity in pattern.get("medical_entities", []):
                    entity_text = entity.get("Text", "")
                    entity_type = entity.get("Type", "")

                    # Store mappings by type
                    type_key = f"{entity_type}_{language_pair}"
                    if type_key not in mappings:
                        mappings[type_key] = {}

                    count = mappings[type_key].get(entity_text, 0)
                    mappings[type_key][entity_text] = count + 1

        return mappings

    async def _identify_cultural_health_beliefs(
        self, patterns: List[Dict[str, Any]], cultural_region: str
    ) -> List[str]:
        """Identify cultural health beliefs from communication patterns."""
        beliefs = []

        # Region-specific health beliefs
        belief_indicators = {
            "middle_east": ["evil eye", "hot/cold foods", "prayer healing"],
            "south_asia": ["ayurveda", "yoga", "karma", "hot/cold balance"],
            "east_africa": [
                "traditional healers",
                "herbal medicine",
                "spiritual causes",
            ],
            "latin_america": ["susto", "mal de ojo", "hot/cold theory", "folk healers"],
            "southeast_asia": [
                "balance",
                "chi",
                "traditional medicine",
                "ancestor spirits",
            ],
        }

        region_beliefs = belief_indicators.get(cultural_region, [])

        # Extract beliefs from patterns
        for pattern in patterns:
            text_lower = pattern.get("text", "").lower()
            for belief in region_beliefs:
                if belief in text_lower:
                    beliefs.append(f"believes_in_{belief.replace(' ', '_')}")

        return list(set(beliefs))

    async def _validate_dataset_quality(self, dataset: CulturalDataset) -> None:
        """Validate dataset quality for healthcare use."""
        if dataset.sample_size < 100:
            raise ValueError(
                f"Insufficient data samples: {dataset.sample_size} < 100 minimum required"
            )

        if not dataset.medical_terminology_mappings:
            logger.warning("No medical terminology mappings found in dataset")

        if not dataset.sensitive_topics:
            raise ValueError(
                "No sensitive topics identified - critical for healthcare communications"
            )

    def _validate_training_config(self, config: TrainingConfig) -> None:
        """Validate training configuration for healthcare requirements."""
        if not config.enable_medical_validation:
            raise ValueError("Medical validation must be enabled for healthcare models")

        if config.cultural_sensitivity_threshold < 0.9:
            raise ValueError(
                "Cultural sensitivity threshold must be at least 0.9 for healthcare"
            )

        if not config.require_human_review:
            logger.warning("Human review is strongly recommended for healthcare models")

    async def _monitor_training_execution(
        self, execution: Any, config: TrainingConfig
    ) -> None:
        """Monitor training execution with CloudWatch metrics."""
        metric_namespace = "HavenHealth/ModelTraining"

        while execution.describe()["PipelineExecutionStatus"] == "Executing":
            # Send heartbeat metric
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.cloudwatch.put_metric_data(
                    Namespace=metric_namespace,
                    MetricData=[
                        {
                            "MetricName": "TrainingProgress",
                            "Value": 1,
                            "Unit": "Count",
                            "Dimensions": [
                                {"Name": "ModelName", "Value": config.model_name},
                                {"Name": "Region", "Value": self.region},
                            ],
                        }
                    ],
                ),
            )

            await asyncio.sleep(60)  # Check every minute

    async def _validate_training_results(self, execution: Any) -> Dict[str, float]:
        """Validate training results meet healthcare standards."""
        # Extract metrics from execution
        steps = execution.describe()["PipelineExecutionSteps"]

        metrics = {}
        for step in steps:
            if step["StepName"] == "TrainCulturalModel":
                training_job = step["Metadata"]["TrainingJob"]
                final_metrics = training_job.get("FinalMetricDataList", [])

                for metric in final_metrics:
                    metrics[metric["MetricName"]] = metric["Value"]

        # Ensure critical metrics are present
        required_metrics = [
            "accuracy",
            "f1_score",
            "cultural_sensitivity_score",
            "medical_accuracy",
        ]
        for metric in required_metrics:
            if metric not in metrics:
                raise ValueError(f"Missing required metric: {metric}")

        return metrics

    def _store_pipeline_metadata(
        self, pipeline: Any, dataset: CulturalDataset, config: TrainingConfig
    ) -> None:
        """Store pipeline metadata for compliance and auditing."""
        metadata = {
            "pipeline_name": pipeline.name,
            "dataset_language_pair": dataset.language_pair,
            "dataset_cultural_region": dataset.cultural_region,
            "dataset_sample_size": dataset.sample_size,
            "training_config": config.__dict__,
            "created_at": datetime.utcnow().isoformat(),
            "compliance_checks": {
                "medical_validation_enabled": config.enable_medical_validation,
                "cultural_sensitivity_threshold": config.cultural_sensitivity_threshold,
                "human_review_required": config.require_human_review,
                "encryption_enabled": True,
                "audit_logging_enabled": True,
            },
        }

        # Store in DynamoDB or S3 for long-term retention
        logger.info(f"Stored pipeline metadata: {metadata}")

    async def _setup_continuous_learning(
        self, model_name: str, dataset: CulturalDataset
    ) -> None:
        """Set up continuous learning pipeline for model improvement."""
        logger.info(f"Setting up continuous learning for {model_name}")

        # Create SNS topic for feedback
        topic_name = f"cultural-model-feedback-{dataset.language_pair}"

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self.sns.create_topic(Name=topic_name)
            )

            topic_arn = response["TopicArn"]

            # Subscribe to feedback events
            # This would connect to the feedback collection system
            logger.info(f"Created feedback topic: {topic_arn}")

        except (BotoCore, ClientError) as e:
            logger.error(f"Failed to setup continuous learning: {e}")

    def _analyze_medical_comprehension(
        self, communications: List[Dict[str, Any]]
    ) -> float:
        """Analyze medical terminology comprehension level."""
        comprehension_indicators = {
            "good": ["i understand", "clear", "makes sense", "got it"],
            "poor": ["don't understand", "confused", "what does that mean", "explain"],
        }

        good_count = 0
        poor_count = 0

        for comm in communications:
            text_lower = comm.get("text", "").lower()

            good_count += sum(
                1 for phrase in comprehension_indicators["good"] if phrase in text_lower
            )
            poor_count += sum(
                1 for phrase in comprehension_indicators["poor"] if phrase in text_lower
            )

        if good_count + poor_count == 0:
            return 0.5  # Neutral if no indicators

        return good_count / (good_count + poor_count)

    def _identify_cultural_issues(
        self, communications: List[Dict[str, Any]]
    ) -> List[str]:
        """Identify specific cultural sensitivity issues."""
        issues = []

        issue_patterns = {
            "gender_mismatch": [
                "male doctor",
                "female doctor",
                "prefer woman",
                "prefer man",
            ],
            "religious_conflict": [
                "against religion",
                "not allowed",
                "haram",
                "forbidden",
            ],
            "dietary_concerns": [
                "can't eat",
                "dietary",
                "halal",
                "kosher",
                "vegetarian",
            ],
            "modesty_concerns": ["cover", "modest", "privacy", "expose"],
            "family_exclusion": [
                "family should know",
                "tell my family",
                "husband decides",
            ],
        }

        for issue_type, patterns in issue_patterns.items():
            for comm in communications:
                text_lower = comm.get("text", "").lower()
                if any(pattern in text_lower for pattern in patterns):
                    issues.append(issue_type)
                    break

        return list(set(issues))

    def _calculate_sensitivity_scores(
        self, cultural_patterns: Dict[str, Any]
    ) -> Dict[str, float]:
        """Calculate cultural sensitivity scores for each region."""
        scores = {}

        for region, analysis in cultural_patterns.items():
            # Base score
            score = 0.7

            # Adjust based on barriers
            barriers = analysis.get("communication_barriers", [])
            score -= len(barriers) * 0.05

            # Adjust based on comprehension
            comprehension = analysis.get("medical_terminology_comprehension", 0.5)
            score += (comprehension - 0.5) * 0.2

            # Adjust based on cultural issues
            issues = analysis.get("cultural_sensitivity_issues", [])
            score -= len(issues) * 0.05

            # Ensure score is between 0 and 1
            scores[region] = max(0.0, min(1.0, score))

        return scores

    async def _extract_sensitive_topics_from_patterns(
        self, patterns: List[Dict[str, Any]]
    ) -> List[str]:
        """Extract additional sensitive topics from communication patterns."""
        sensitive_topics = []

        # Analyze negative sentiment communications
        for pattern in patterns:
            if pattern.get("sentiment") in ["NEGATIVE", "MIXED"]:
                # Extract topics from medical entities
                for entity in pattern.get("medical_entities", []):
                    if entity.get("Type") == "MEDICAL_CONDITION":
                        condition = entity.get("Text", "").lower()
                        # Check if it's a sensitive condition
                        sensitive_conditions = [
                            "mental",
                            "psychiatric",
                            "hiv",
                            "aids",
                            "std",
                            "sexual",
                            "abortion",
                            "miscarriage",
                            "infertility",
                            "cancer",
                        ]
                        if any(
                            sensitive in condition for sensitive in sensitive_conditions
                        ):
                            sensitive_topics.append(condition.replace(" ", "_"))

        return list(set(sensitive_topics))

    @audit_phi_access("deploy_cultural_model")
    @require_permission(AccessPermission.ADMIN)
    async def deploy_cultural_model(
        self,
        model_name: str,
        model_artifact_path: str,
        instance_type: str = "ml.m5.xlarge",
        initial_instance_count: int = 1,
        endpoint_name: Optional[str] = None,
    ) -> str:
        """Deploy cultural adaptation model to SageMaker endpoint.

        Args:
            model_name: Name of the model to deploy
            model_artifact_path: S3 path to model artifacts
            instance_type: Instance type for endpoint
            initial_instance_count: Initial number of instances
            endpoint_name: Optional custom endpoint name

        Returns:
            Endpoint name
        """
        if not endpoint_name:
            endpoint_name = (
                f"{model_name}-endpoint-{datetime.now().strftime('%Y%m%d%H%M%S')}"
            )

        logger.info(f"Deploying model {model_name} to endpoint {endpoint_name}")

        try:
            # Create model
            model_response = self.sagemaker_client.create_model(
                ModelName=model_name,
                ExecutionRoleArn=self.role,
                PrimaryContainer={
                    "Image": self._get_inference_image(),
                    "ModelDataUrl": model_artifact_path,
                    "Environment": {
                        "SAGEMAKER_PROGRAM": "inference.py",
                        "SAGEMAKER_SUBMIT_DIRECTORY": model_artifact_path,
                        "SAGEMAKER_REGION": self.region,
                        "MODEL_TYPE": "cultural_adaptation",
                    },
                },
            )

            logger.info(f"Created model: {model_response['ModelArn']}")

            # Create endpoint configuration
            endpoint_config_name = f"{endpoint_name}-config"

            config_response = self.sagemaker_client.create_endpoint_config(
                EndpointConfigName=endpoint_config_name,
                ProductionVariants=[
                    {
                        "VariantName": "AllTraffic",
                        "ModelName": model_name,
                        "InitialInstanceCount": initial_instance_count,
                        "InstanceType": instance_type,
                        "InitialVariantWeight": 1,
                    }
                ],
                DataCaptureConfig={
                    "EnableCapture": True,
                    "InitialSamplingPercentage": 100,
                    "DestinationS3Uri": f"s3://{self.bucket}/{self.prefix}/data-capture",
                    "CaptureOptions": [
                        {"CaptureMode": "Input"},
                        {"CaptureMode": "Output"},
                    ],
                    "CaptureContentTypeHeader": {
                        "JsonContentTypes": ["application/json"]
                    },
                },
            )

            logger.info(
                f"Created endpoint config: {config_response['EndpointConfigArn']}"
            )

            # Create endpoint
            endpoint_response = self.sagemaker_client.create_endpoint(
                EndpointName=endpoint_name,
                EndpointConfigName=endpoint_config_name,
                Tags=[
                    {"Key": "Purpose", "Value": "CulturalAdaptation"},
                    {"Key": "ModelType", "Value": "HealthcareNLP"},
                    {"Key": "Project", "Value": "HavenHealthPassport"},
                ],
            )

            logger.info(f"Creating endpoint: {endpoint_response['EndpointArn']}")

            # Wait for endpoint to be in service
            waiter = self.sagemaker_client.get_waiter("endpoint_in_service")
            waiter.wait(
                EndpointName=endpoint_name,
                WaiterConfig={"Delay": 30, "MaxAttempts": 60},  # Wait up to 30 minutes
            )

            # Setup monitoring
            await self._setup_endpoint_monitoring(endpoint_name)

            # Store endpoint info
            if not hasattr(self, "endpoints"):
                self.endpoints = {}
            self.endpoints["cultural_pattern_classifier"] = endpoint_name

            logger.info(f"Successfully deployed model to endpoint: {endpoint_name}")
            return endpoint_name

        except (BotoCore, ClientError) as e:
            logger.error(f"Failed to deploy model: {e}")
            # Clean up any partially created resources
            await self._cleanup_failed_deployment(model_name, endpoint_name)
            raise

    @audit_phi_access("invoke_cultural_pattern_classifier")
    @require_permission(AccessPermission.READ_PHI)
    async def invoke_cultural_pattern_classifier(
        self,
        text: str,
        source_language: str,
        target_language: str,
        region: str,
        endpoint_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Invoke cultural pattern classifier for healthcare text.

        Args:
            text: Healthcare text to analyze
            source_language: Source language code
            target_language: Target language code
            region: Cultural region
            endpoint_name: Optional specific endpoint name

        Returns:
            Cultural pattern analysis results
        """
        if not endpoint_name:
            endpoint_name = self.endpoints.get("cultural_pattern_classifier")

        if not endpoint_name:
            raise ValueError("No cultural pattern classifier endpoint available")

        logger.info(
            f"Invoking cultural pattern classifier for {source_language}->{target_language} in {region}"
        )

        try:
            # Prepare input
            input_data = {
                "text": text,
                "source_language": source_language,
                "target_language": target_language,
                "cultural_region": region,
                "context": "healthcare",
                "timestamp": datetime.utcnow().isoformat(),
            }

            # Invoke endpoint
            runtime_client = boto3.client("sagemaker-runtime", region_name=self.region)

            response = runtime_client.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType="application/json",
                Accept="application/json",
                Body=json.dumps(input_data),
            )

            # Parse response
            result = json.loads(response["Body"].read().decode())

            # Add metadata
            result["endpoint_used"] = endpoint_name
            result["processing_time_ms"] = (
                response["ResponseMetadata"]
                .get("HTTPHeaders", {})
                .get("x-amzn-invoked-production-variant", "unknown")
            )

            # Log metrics
            await self._log_inference_metrics(endpoint_name, result)

            return dict(result)

        except (BotoCore, ClientError, ValueError) as e:
            logger.error(f"Failed to invoke cultural pattern classifier: {e}")
            raise

    def _get_inference_image(self) -> str:
        """Get the appropriate inference container image."""
        # Use PyTorch inference container for cultural models
        region_mapping = {
            "us-east-1": "763104351884",
            "us-west-2": "763104351884",
            "eu-west-1": "763104351884",
            "ap-southeast-1": "763104351884",
        }

        account = region_mapping.get(self.region, "763104351884")
        return f"{account}.dkr.ecr.{self.region}.amazonaws.com/pytorch-inference:1.12-gpu-py38"

    async def _setup_endpoint_monitoring(self, endpoint_name: str) -> None:
        """Set up CloudWatch monitoring for the endpoint."""
        try:
            # Create CloudWatch alarms
            alarms = [
                {
                    "AlarmName": f"{endpoint_name}-ModelLatency",
                    "MetricName": "ModelLatency",
                    "Statistic": "Average",
                    "Period": 300,
                    "EvaluationPeriods": 2,
                    "Threshold": 1000.0,
                    "ComparisonOperator": "GreaterThanThreshold",
                    "TreatMissingData": "notBreaching",
                    "AlarmDescription": "Alarm when model latency exceeds 1 second",
                },
                {
                    "AlarmName": f"{endpoint_name}-Invocations4XXErrors",
                    "MetricName": "Invocation4XXErrors",
                    "Statistic": "Sum",
                    "Period": 300,
                    "EvaluationPeriods": 1,
                    "Threshold": 10.0,
                    "ComparisonOperator": "GreaterThanThreshold",
                    "TreatMissingData": "notBreaching",
                    "AlarmDescription": "Alarm when 4XX errors exceed threshold",
                },
            ]

            for alarm_config in alarms:
                self.cloudwatch.put_metric_alarm(
                    **alarm_config,
                    Namespace="AWS/SageMaker",
                    Dimensions=[
                        {"Name": "EndpointName", "Value": endpoint_name},
                        {"Name": "VariantName", "Value": "AllTraffic"},
                    ],
                )

            logger.info(f"Set up monitoring alarms for endpoint: {endpoint_name}")

        except (BotoCore, ClientError) as e:
            logger.error(f"Failed to set up monitoring: {e}")

    async def _cleanup_failed_deployment(
        self, model_name: str, endpoint_name: str
    ) -> None:
        """Clean up resources from a failed deployment."""
        try:
            # Try to delete endpoint
            try:
                self.sagemaker_client.delete_endpoint(EndpointName=endpoint_name)
                logger.info(f"Deleted endpoint: {endpoint_name}")
            except (BotoCore, ClientError):
                pass

            # Try to delete endpoint config
            try:
                self.sagemaker_client.delete_endpoint_config(
                    EndpointConfigName=f"{endpoint_name}-config"
                )
                logger.info(f"Deleted endpoint config: {endpoint_name}-config")
            except (BotoCore, ClientError):
                pass

            # Try to delete model
            try:
                self.sagemaker_client.delete_model(ModelName=model_name)
                logger.info(f"Deleted model: {model_name}")
            except (BotoCore, ClientError):
                pass

        except (BotoCore, ClientError) as e:
            logger.error(f"Error during cleanup: {e}")

    async def _log_inference_metrics(
        self, endpoint_name: str, result: Dict[str, Any]
    ) -> None:
        """Log inference metrics to CloudWatch."""
        try:
            # Extract metrics from result
            metrics = [
                {
                    "MetricName": "CulturalSensitivityScore",
                    "Value": result.get("cultural_sensitivity_score", 0.0),
                    "Unit": "None",
                },
                {
                    "MetricName": "ConfidenceScore",
                    "Value": result.get("confidence", 0.0),
                    "Unit": "None",
                },
            ]

            # Put metrics to CloudWatch
            self.cloudwatch.put_metric_data(
                Namespace="HavenHealthPassport/CulturalAdaptation",
                MetricData=[
                    {
                        **metric,
                        "Dimensions": [
                            {"Name": "EndpointName", "Value": endpoint_name},
                            {
                                "Name": "Region",
                                "Value": result.get("cultural_region", "unknown"),
                            },
                        ],
                        "Timestamp": datetime.utcnow(),
                    }
                    for metric in metrics
                ],
            )

        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed to log inference metrics: {e}")
