"""Model access configuration for Haven Health Passport."""

from pathlib import Path

from dotenv import load_dotenv

# Load AWS environment
env_path = Path(__file__).parent.parent.parent.parent / ".env.aws"
if env_path.exists():
    load_dotenv(env_path)

# Role-based model access permissions
ROLE_PERMISSIONS = {
    "healthcare_provider": {
        "access_level": "premium",
        "allowed_models": [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-v2:1",
            "anthropic.claude-v2",
            "anthropic.claude-instant-v1",
        ],
        "rate_limit": 100,
        "daily_token_limit": 5000000,
        "cost_limit": 500.0,
    },
    "refugee_user": {
        "access_level": "basic",
        "allowed_models": [
            "anthropic.claude-instant-v1",
            "amazon.titan-text-lite-v1",
        ],
        "rate_limit": 20,
        "daily_token_limit": 100000,
        "cost_limit": 10.0,
    },
    "aid_worker": {
        "access_level": "standard",
        "allowed_models": [
            "anthropic.claude-v2",
            "anthropic.claude-instant-v1",
            "amazon.titan-text-express-v1",
        ],
        "rate_limit": 50,
        "daily_token_limit": 1000000,
        "cost_limit": 100.0,
    },
}
