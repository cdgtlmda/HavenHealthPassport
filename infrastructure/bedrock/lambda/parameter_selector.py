"""
Bedrock Inference Parameter Selector
Dynamically selects and merges inference parameters based on use case and context
"""

import json
import logging
import os
from copy import deepcopy
from typing import Any, Dict, Optional

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load configuration from environment
BASE_PARAMS = json.loads(os.environ.get("BASE_PARAMS_JSON", "{}"))
MEDICAL_PARAMS = json.loads(os.environ.get("MEDICAL_PARAMS_JSON", "{}"))
PROFILES = json.loads(os.environ.get("PROFILES_JSON", "{}"))
ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")


class ParameterSelector:
    """Handles dynamic parameter selection and merging"""

    def __init__(self):
        self.base_params = BASE_PARAMS
        self.medical_params = MEDICAL_PARAMS
        self.profiles = PROFILES

    def select_parameters(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Select and merge parameters based on request context"""
        model_family = request.get("model_family", "claude")
        use_case = request.get("use_case", "general")
        profile = request.get("profile", "balanced")
        custom_params = request.get("custom_params", {})

        # Start with base parameters for model family
        params = deepcopy(self.base_params.get(model_family, {}))

        # Apply use case specific parameters
        if use_case in self.medical_params:
            params = self.merge_params(params, self.medical_params[use_case])

        # Apply profile overrides
        if profile in self.profiles:
            params = self.merge_params(params, self.profiles[profile])

        # Apply custom parameters last (highest priority)
        if custom_params:
            params = self.merge_params(params, custom_params)
        # Apply safety validations
        params = self.apply_safety_checks(params, use_case)

        # Log parameter selection
        logger.info(
            f"Selected parameters for {use_case}/{profile}: {json.dumps(params)}"
        )

        return params

    def merge_params(
        self, base: Dict[str, Any], override: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Deep merge parameters with override taking precedence"""
        result = deepcopy(base)

        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self.merge_params(result[key], value)
            else:
                result[key] = value

        return result

    def apply_safety_checks(
        self, params: Dict[str, Any], use_case: str
    ) -> Dict[str, Any]:
        """Apply safety validations and limits"""
        # Medical use cases require stricter parameters
        if "medical" in use_case:
            # Ensure low temperature for accuracy
            if params.get("temperature", 0) > 0.3:
                params["temperature"] = 0.3
                logger.warning(f"Capped temperature to 0.3 for medical use case")

            # Ensure safety mode is enabled
            params["safety_mode"] = "maximum"

            # Require higher confidence thresholds
            if "min_confidence_score" in params:
                params["min_confidence_score"] = max(
                    params["min_confidence_score"], 0.9
                )

        # Apply token limits based on environment
        if ENVIRONMENT == "prod":
            max_allowed = 16384
        else:
            max_allowed = 8192

        if params.get("max_tokens", 0) > max_allowed:
            params["max_tokens"] = max_allowed
            logger.warning(f"Capped max_tokens to {max_allowed}")

        return params

    def get_model_specific_format(
        self, model_family: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Convert parameters to model-specific format"""
        if model_family == "claude":
            # Claude format
            return {
                "max_tokens": params.get("max_tokens", 4096),
                "temperature": params.get("temperature", 0.7),
                "top_p": params.get("top_p", 1.0),
                "top_k": params.get("top_k", 250),
                "stop_sequences": params.get("stop_sequences", []),
                "metadata": {
                    "user_id": params.get("user_id"),
                    "use_case": params.get("use_case"),
                },
            }
        elif model_family == "titan":
            # Titan format
            return {
                "textGenerationConfig": {
                    "maxTokenCount": params.get("maxTokenCount", 8192),
                    "temperature": params.get("temperature", 0.5),
                    "topP": params.get("topP", 0.9),
                    "stopSequences": params.get("stopSequences", []),
                }
            }
        else:
            return params


def handler(event, context):
    """Lambda handler for parameter selection"""
    try:
        # Parse request
        body = json.loads(event.get("body", "{}"))

        # Initialize selector
        selector = ParameterSelector()

        # Select parameters
        params = selector.select_parameters(body)

        # Format for specific model if requested
        if body.get("format_for_model"):
            model_family = body.get("model_family", "claude")
            params = selector.get_model_specific_format(model_family, params)

        return {
            "statusCode": 200,
            "body": json.dumps(params),
            "headers": {"Content-Type": "application/json"},
        }
    except Exception as e:
        logger.error(f"Parameter selection error: {str(e)}")
        return {
            "statusCode": 500,
            "body": json.dumps(
                {"error": "Parameter selection failed", "message": str(e)}
            ),
            "headers": {"Content-Type": "application/json"},
        }
