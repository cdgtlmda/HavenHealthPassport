"""
Bedrock Model Selection Logic
Intelligent model selection based on request characteristics and business rules
"""

import json
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
lambda_client = boto3.client('lambda')
cloudwatch = boto3.client('cloudwatch')

# Environment variables
ENDPOINT_SELECTOR_ARN = os.environ.get('ENDPOINT_SELECTOR_ARN')
PARAMETER_SELECTOR_ARN = os.environ.get('PARAMETER_SELECTOR_ARN')
VERSION_MANAGER_ARN = os.environ.get('VERSION_MANAGER_ARN')
FALLBACK_ORCHESTRATOR_ARN = os.environ.get('FALLBACK_ORCHESTRATOR_ARN')
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')

class RequestComplexity(Enum):
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"

class RequestPriority(Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ModelSelectionContext:
    """Context for model selection decision"""
    use_case: str
    complexity: RequestComplexity
    priority: RequestPriority
    user_tier: str
    estimated_tokens: int
    requires_multimodal: bool
    language: Optional[str] = None    domain_specific: bool = False
    compliance_requirements: List[str] = None

class ModelSelector:
    """Orchestrates intelligent model selection"""

    def __init__(self):
        self.selection_rules = self.load_selection_rules()

    def load_selection_rules(self) -> Dict[str, Any]:
        """Load model selection rules"""
        return {
            'complexity_mapping': {
                RequestComplexity.SIMPLE: ['claude_instant', 'titan_text_express'],
                RequestComplexity.MEDIUM: ['claude_3_sonnet', 'titan_text_express'],
                RequestComplexity.COMPLEX: ['claude_3_opus', 'claude_3_sonnet']
            },
            'priority_boost': {
                RequestPriority.CRITICAL: 'claude_3_opus',
                RequestPriority.HIGH: 'claude_3_sonnet'
            },
            'multimodal_models': ['claude_3_sonnet_multimodal'],
            'translation_models': ['titan_text_express', 'claude_3_sonnet'],
            'embedding_models': ['titan_embeddings_v2', 'titan_embeddings_v1']
        }

    def select_model(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Main model selection logic"""
        try:
            # Parse request context
            context = self.parse_request_context(request)

            # Determine base model based on use case
            base_model = self.determine_base_model(context)

            # Get model version
            version_info = self.get_model_version(base_model, context)

            # Select endpoint configuration
            endpoint_config = self.select_endpoint(base_model, context)

            # Get inference parameters
            inference_params = self.get_inference_parameters(base_model, context)

            # Build final configuration
            model_config = self.build_model_configuration(
                base_model, version_info, endpoint_config, inference_params, context
            )

            # Log selection decision
            self.log_selection_metrics(context, model_config)
            return model_config

        except Exception as e:
            logger.error(f"Model selection failed: {str(e)}")
            # Return fallback configuration
            return self.get_fallback_configuration(request)

    def parse_request_context(self, request: Dict[str, Any]) -> ModelSelectionContext:
        """Parse request to extract selection context"""
        # Analyze request complexity
        complexity = self.analyze_complexity(request)

        # Determine priority
        priority = RequestPriority(request.get('priority', 'normal'))

        # Check multimodal requirements
        requires_multimodal = self.check_multimodal_requirements(request)

        return ModelSelectionContext(
            use_case=request.get('use_case', 'general'),
            complexity=complexity,
            priority=priority,
            user_tier=request.get('user_tier', 'standard'),
            estimated_tokens=self.estimate_tokens(request),
            requires_multimodal=requires_multimodal,
            language=request.get('language'),
            domain_specific=request.get('domain_specific', False),
            compliance_requirements=request.get('compliance_requirements', [])
        )

    def analyze_complexity(self, request: Dict[str, Any]) -> RequestComplexity:
        """Analyze request complexity"""
        estimated_tokens = self.estimate_tokens(request)

        if estimated_tokens < 1000:
            return RequestComplexity.SIMPLE
        elif estimated_tokens < 4000:
            return RequestComplexity.MEDIUM
        else:
            return RequestComplexity.COMPLEX

    def estimate_tokens(self, request: Dict[str, Any]) -> int:
        """Estimate token count for request"""
        # Simplified estimation - would use tokenizer in production
        text = json.dumps(request.get('messages', []))
        return len(text) // 4  # Rough approximation
    def check_multimodal_requirements(self, request: Dict[str, Any]) -> bool:
        """Check if request requires multimodal capabilities"""
        messages = request.get('messages', [])
        for message in messages:
            if isinstance(message.get('content'), list):
                for content in message['content']:
                    if content.get('type') == 'image':
                        return True
        return False

    def determine_base_model(self, context: ModelSelectionContext) -> str:
        """Determine base model based on context"""
        # Priority overrides
        if context.priority in self.selection_rules['priority_boost']:
            return self.selection_rules['priority_boost'][context.priority]

        # Multimodal requirements
        if context.requires_multimodal:
            return self.selection_rules['multimodal_models'][0]

        # Translation use case
        if context.use_case == 'medical_translation':
            return self.selection_rules['translation_models'][0]

        # Embedding use case
        if context.use_case == 'embeddings':
            return self.selection_rules['embedding_models'][0]

        # Complexity-based selection
        complexity_models = self.selection_rules['complexity_mapping'][context.complexity]

        # User tier adjustment
        if context.user_tier == 'premium' and context.complexity != RequestComplexity.SIMPLE:
            return 'claude_3_opus'

        return complexity_models[0]

    def get_model_version(self, base_model: str, context: ModelSelectionContext) -> Dict[str, Any]:
        """Get appropriate model version"""
        try:
            # Determine channel based on context
            channel = 'stable'
            if context.user_tier == 'beta':
                channel = 'preview'
            elif context.priority == RequestPriority.LOW:
                channel = 'legacy'  # Use older, cheaper models for low priority
            # Call version manager
            response = lambda_client.invoke(
                FunctionName=VERSION_MANAGER_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'action': 'select',
                    'model_family': self.get_model_family(base_model),
                    'channel': channel,
                    'user_id': context.user_tier
                })
            )

            return json.loads(response['Payload'].read())

        except Exception as e:
            logger.error(f"Version selection failed: {str(e)}")
            return {'model_id': base_model, 'version': 'default'}

    def select_endpoint(self, base_model: str, context: ModelSelectionContext) -> Dict[str, Any]:
        """Select endpoint configuration"""
        try:
            response = lambda_client.invoke(
                FunctionName=ENDPOINT_SELECTOR_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'use_case': context.use_case,
                    'context': {
                        'priority': context.priority.value,
                        'estimated_tokens': context.estimated_tokens
                    }
                })
            )

            return json.loads(response['Payload'].read())

        except Exception as e:
            logger.error(f"Endpoint selection failed: {str(e)}")
            return {'model_key': base_model}

    def get_inference_parameters(self, base_model: str,
                                context: ModelSelectionContext) -> Dict[str, Any]:
        """Get optimized inference parameters"""
        try:
            # Determine profile based on context
            profile = 'balanced'
            if context.priority == RequestPriority.CRITICAL:
                profile = 'detailed_analysis'
            elif context.priority == RequestPriority.LOW:
                profile = 'cost_optimized'
            response = lambda_client.invoke(
                FunctionName=PARAMETER_SELECTOR_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'model_family': self.get_model_family(base_model),
                    'use_case': context.use_case,
                    'profile': profile,
                    'format_for_model': True,
                    'custom_params': {
                        'max_tokens': min(context.estimated_tokens * 2, 16384)
                    }
                })
            )

            return json.loads(response['Payload'].read())

        except Exception as e:
            logger.error(f"Parameter selection failed: {str(e)}")
            return {'temperature': 0.7, 'max_tokens': 4096}

    def build_model_configuration(self, base_model: str, version_info: Dict[str, Any],
                                endpoint_config: Dict[str, Any],
                                inference_params: Dict[str, Any],
                                context: ModelSelectionContext) -> Dict[str, Any]:
        """Build complete model configuration"""
        config = {
            'model_key': base_model,
            'model_id': version_info.get('model_id', base_model),
            'version': version_info.get('version', 'default'),
            'endpoint': endpoint_config,
            'parameters': inference_params,
            'use_fallback': context.priority != RequestPriority.LOW,
            'enable_caching': context.priority != RequestPriority.CRITICAL,
            'metadata': {
                'use_case': context.use_case,
                'complexity': context.complexity.value,
                'priority': context.priority.value,
                'requires_multimodal': context.requires_multimodal,
                'selected_at': time.time()
            }
        }

        # Add compliance flags if needed
        if context.compliance_requirements:
            config['compliance'] = {
                'requirements': context.compliance_requirements,
                'audit_enabled': True,
                'data_retention': 'minimal'
            }

        return config
    def get_model_family(self, model_key: str) -> str:
        """Extract model family from model key"""
        if 'claude' in model_key:
            return 'claude'
        elif 'titan' in model_key:
            return 'titan'
        else:
            return 'unknown'

    def get_fallback_configuration(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Return fallback configuration when selection fails"""
        return {
            'model_key': 'claude_3_sonnet',
            'model_id': 'anthropic.claude-3-sonnet-20240229',
            'version': 'stable',
            'parameters': {
                'temperature': 0.7,
                'max_tokens': 4096
            },
            'use_fallback': True,
            'fallback_reason': 'selection_failure'
        }

    def log_selection_metrics(self, context: ModelSelectionContext,
                            config: Dict[str, Any]):
        """Log model selection metrics"""
        try:
            cloudwatch.put_metric_data(
                Namespace='HavenHealthPassport/Bedrock',
                MetricData=[{
                    'MetricName': 'ModelSelection',
                    'Value': 1,
                    'Unit': 'Count',
                    'Dimensions': [
                        {'Name': 'UseCase', 'Value': context.use_case},
                        {'Name': 'Model', 'Value': config['model_key']},
                        {'Name': 'Complexity', 'Value': context.complexity.value},
                        {'Name': 'Priority', 'Value': context.priority.value},
                        {'Name': 'Environment', 'Value': ENVIRONMENT}
                    ]
                }]
            )
        except Exception as e:
            logger.warning(f"Failed to log metrics: {str(e)}")
def handler(event, context):
    """Lambda handler for model selection"""
    try:
        # Parse request
        body = json.loads(event.get('body', '{}'))

        # Initialize selector
        selector = ModelSelector()

        # Select model configuration
        model_config = selector.select_model(body)

        # If fallback is enabled, wrap with fallback orchestrator
        if model_config.get('use_fallback', True):
            response = lambda_client.invoke(
                FunctionName=FALLBACK_ORCHESTRATOR_ARN,
                InvocationType='RequestResponse',
                Payload=json.dumps({
                    'use_case': body.get('use_case', 'general'),
                    'body': body,
                    'primary_model': model_config
                })
            )

            return json.loads(response['Payload'].read())
        else:
            # Return direct configuration
            return {
                'statusCode': 200,
                'body': json.dumps(model_config),
                'headers': {'Content-Type': 'application/json'}
            }

    except Exception as e:
        logger.error(f"Model selection error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Model selection failed',
                'message': str(e),
                'fallback_config': ModelSelector().get_fallback_configuration({})
            }),
            'headers': {'Content-Type': 'application/json'}
        }
