#!/usr/bin/env python3
"""Check and display Bedrock cost monitoring setup."""

import os
from datetime import datetime, timedelta
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# Load AWS credentials
env_path = Path(__file__).parent.parent.parent / '.env.aws'
if env_path.exists():
    with open(env_path, 'r') as f:
        for line in f:
            if line.strip() and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ[key] = value


def check_bedrock_costs():
    """Check current Bedrock costs using Cost Explorer."""
    ce_client = boto3.client('ce')

    # Get costs for the last 7 days
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=7)

    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date.strftime('%Y-%m-%d'),
                'End': end_date.strftime('%Y-%m-%d')
            },
            Granularity='DAILY',
            Metrics=['UnblendedCost'],
            Filter={
                'Dimensions': {
                    'Key': 'SERVICE',
                    'Values': ['Amazon Bedrock']
                }
            }
        )

        print("=" * 60)
        print("Bedrock Cost Report (Last 7 Days)")
        print("=" * 60)

        total_cost = 0.0
        for result in response['ResultsByTime']:
            date = result['TimePeriod']['Start']
            cost = float(result['Total']['UnblendedCost']['Amount'])
            total_cost += cost
            if cost > 0:
                print(f"{date}: ${cost:.2f}")
