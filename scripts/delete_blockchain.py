#!/usr/bin/env python3
"""Delete blockchain resources to save costs."""

import boto3
import os
import sys

# Safety check
print("⚠️  WARNING: This will delete the blockchain network!")
print("Network ID: n-KIKQ7YMKBJD7PNQRXODQNCQNHE")
print("This will save you $1,633 over 2 months.")
response = input("\nType 'DELETE' to confirm: ")

if response != "DELETE":
    print("Cancelled.")
    sys.exit(0)

# Load credentials
os.system('export $(cat .env.aws | grep -v "^#" | xargs)')

blockchain = boto3.client('managedblockchain', region_name='us-east-1')

try:
    # Delete member first
    print("\nDeleting member...")
    blockchain.delete_member(
        NetworkId='n-KIKQ7YMKBJD7PNQRXODQNCQNHE',
        MemberId='m-UTEDQF6YOVEUTCSIU6YPSBFJU4'
    )
    print("✅ Member deletion initiated")
    print("⏳ Wait 5-10 minutes before deleting network")
    
except Exception as e:
    print(f"Error: {e}")
    print("\nTry deleting via AWS Console instead")
