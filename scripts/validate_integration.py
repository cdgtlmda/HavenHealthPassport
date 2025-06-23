#!/usr/bin/env python3
"""
Integration validation script for Haven Health Passport
Tests all major component integrations
"""

import asyncio
import aiohttp
import json
import sys
from datetime import datetime

BASE_URL = "http://localhost:8000"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

async def check_service_health(session, name, url):
    """Check if a service is healthy"""
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                print(f"{Colors.GREEN}✓{Colors.END} {name} is healthy")
                return True
            else:
                print(f"{Colors.RED}✗{Colors.END} {name} returned status {response.status}")
                return False
    except Exception as e:
        print(f"{Colors.RED}✗{Colors.END} {name} is not reachable: {str(e)}")
        return False

async def test_api_endpoints(session):
    """Test main API endpoints"""
    print(f"\n{Colors.BLUE}Testing API Endpoints:{Colors.END}")
    
    endpoints = [
        ("Main API", f"{BASE_URL}/"),
        ("API Info", f"{BASE_URL}/api"),
        ("Health Check", f"{BASE_URL}/health"),
        ("GraphQL", f"{BASE_URL}/graphql"),
    ]
    
    results = []
    for name, url in endpoints:
        result = await check_service_health(session, name, url)
        results.append(result)
    
    return all(results)

async def test_authentication_flow(session):
    """Test authentication integration"""
    print(f"\n{Colors.BLUE}Testing Authentication Flow:{Colors.END}")
    
    # Test registration endpoint exists
    try:
        async with session.post(
            f"{BASE_URL}/api/v2/auth/register",
            json={
                "username": "test_user",
                "password": "Test123!@#",
                "email": "test@example.com",
                "firstName": "Test",
                "lastName": "User",
                "dateOfBirth": "1990-01-01"
            }
        ) as response:
            if response.status in [200, 201]:
                print(f"{Colors.GREEN}✓{Colors.END} Registration endpoint working")
                return True
            elif response.status == 409:
                print(f"{Colors.YELLOW}⚠{Colors.END} User already exists (expected)")
                return True
            else:
                print(f"{Colors.RED}✗{Colors.END} Registration failed: {response.status}")
                return False
    except Exception as e:
        print(f"{Colors.RED}✗{Colors.END} Registration endpoint error: {str(e)}")
        return False

async def test_service_integration(session):
    """Test service layer integrations"""
    print(f"\n{Colors.BLUE}Testing Service Integrations:{Colors.END}")
    
    # Check if sync endpoint exists
    try:
        async with session.get(f"{BASE_URL}/api/v2/sync/status") as response:
            if response.status in [200, 401]:  # 401 is ok, means endpoint exists
                print(f"{Colors.GREEN}✓{Colors.END} Sync service integrated")
            else:
                print(f"{Colors.RED}✗{Colors.END} Sync service issue: {response.status}")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠{Colors.END} Sync service not reachable")
    
    # Check if translation endpoint exists
    try:
        async with session.post(
            f"{BASE_URL}/api/v2/translations/translate",
            json={"text": "Hello", "target_language": "es"}
        ) as response:
            if response.status in [200, 401]:
                print(f"{Colors.GREEN}✓{Colors.END} Translation service integrated")
            else:
                print(f"{Colors.RED}✗{Colors.END} Translation service issue")
    except Exception as e:
        print(f"{Colors.YELLOW}⚠{Colors.END} Translation service not reachable")

async def test_infrastructure_services():
    """Test infrastructure services"""
    print(f"\n{Colors.BLUE}Testing Infrastructure Services:{Colors.END}")
    
    services = [
        ("PostgreSQL", "5432"),
        ("Redis", "6379"),
        ("MinIO (S3)", "9000"),
        ("OpenSearch", "9200"),
        ("FHIR Server", "8080"),
    ]
    
    for service, port in services:
        try:
            reader, writer = await asyncio.open_connection('localhost', int(port))
            writer.close()
            await writer.wait_closed()
            print(f"{Colors.GREEN}✓{Colors.END} {service} is running on port {port}")
        except Exception:
            print(f"{Colors.RED}✗{Colors.END} {service} is not accessible on port {port}")

async def main():
    """Run all integration tests"""
    print(f"{Colors.BLUE}Haven Health Passport Integration Validation{Colors.END}")
    print("=" * 50)
    
    async with aiohttp.ClientSession() as session:
        # Test API endpoints
        api_ok = await test_api_endpoints(session)
        
        # Test authentication
        auth_ok = await test_authentication_flow(session)
        
        # Test service integrations
        await test_service_integration(session)
    
    # Test infrastructure
    await test_infrastructure_services()
    
    print("\n" + "=" * 50)
    if api_ok and auth_ok:
        print(f"{Colors.GREEN}✓ Core integration is functional!{Colors.END}")
        print("\nYour Haven Health Passport is ready to use:")
        print(f"  - API: {BASE_URL}")
        print(f"  - API Docs: {BASE_URL}/api/docs")
        print(f"  - GraphQL: {BASE_URL}/graphql")
        print(f"  - Web Portal: http://localhost:3000")
        return 0
    else:
        print(f"{Colors.RED}✗ Some integrations need attention{Colors.END}")
        print("\nRun 'docker-compose up -d' to start all services")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
