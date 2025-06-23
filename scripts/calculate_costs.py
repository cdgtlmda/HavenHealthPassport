#!/usr/bin/env python3
"""Calculate and manage AWS costs for Haven Health Passport."""

import boto3

blockchain = boto3.client('managedblockchain', region_name='us-east-1')

print('💰 HAVEN HEALTH PASSPORT - AWS COST ANALYSIS')
print('=' * 60)

# Blockchain costs
elapsed_hours = 0.3  # ~18 minutes
network_cost = elapsed_hours * 0.50
member_cost = elapsed_hours * 0.10
total_so_far = network_cost + member_cost

print(f'\n🔗 BLOCKCHAIN COSTS:')
print(f'   Running for: ~18 minutes')
print(f'   Cost so far: ${total_so_far:.2f}')
print(f'   Cost per hour: $0.60')
print(f'   Cost per day: ${0.60 * 24:.2f}')
print(f'   Cost per month: ${0.60 * 24 * 30:.2f}')
print(f'   Cost for 2 months: ${0.60 * 24 * 60:.2f}')

print(f'\n📊 TOTAL PROJECT COSTS (2 MONTHS):')
print(f'   Option 1 - Everything: ~$2,160')
print(f'   Option 2 - No Blockchain: ~$527')
print(f'   Option 3 - Minimal (Bedrock+S3): ~$110')

print(f'\n🎯 FOR JUDGING PERIOD:')
print(f'   Recommended: Option 3 - Minimal')
print(f'   - Core translation works perfectly')
print(f'   - Mock blockchain for demo')
print(f'   - Mock HealthLake for demo')
print(f'   - Only pay for actual API usage')

print(f'\n⚠️  ACTION REQUIRED:')
print(f'   DELETE the blockchain to save $1,633!')
print(f'   Network ID: n-KIKQ7YMKBJD7PNQRXODQNCQNHE')
print(f'   Member ID: m-UTEDQF6YOVEUTCSIU6YPSBFJU4')
