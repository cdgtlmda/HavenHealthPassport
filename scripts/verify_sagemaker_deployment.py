#!/usr/bin/env python3
"""Verify SageMaker deployment for cultural adaptation models.

CRITICAL: This verifies healthcare AI models are properly deployed
and meeting performance requirements for refugee care.
"""

import argparse
import json
import time
import boto3
from datetime import datetime
import logging
import asyncio
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SageMakerDeploymentVerifier:
    """Verify SageMaker deployments meet healthcare standards."""
    
    def __init__(self, region: str = "us-east-1"):
        """Initialize verifier."""
        self.region = region
        self.sagemaker_client = boto3.client("sagemaker", region_name=region)
        self.sagemaker_runtime = boto3.client("sagemaker-runtime", region_name=region)
        self.cloudwatch = boto3.client("cloudwatch", region_name=region)
        
        # Healthcare performance thresholds
        self.thresholds = {
            'latency_ms': 500,  # Max 500ms for real-time translation
            'error_rate': 0.01,  # Max 1% error rate
            'availability': 0.999,  # 99.9% availability
            'cultural_sensitivity': 0.95  # Min 95% cultural sensitivity
        }    
    async def verify_deployment(self, endpoint_name: str) -> Dict[str, Any]:
        """Verify a single endpoint deployment."""
        logger.info(f"Verifying deployment: {endpoint_name}")
        
        verification_results = {
            'endpoint_name': endpoint_name,
            'timestamp': datetime.utcnow().isoformat(),
            'status': 'unknown',
            'checks': {}
        }
        
        try:
            # Check endpoint status
            endpoint_check = await self._check_endpoint_status(endpoint_name)
            verification_results['checks']['endpoint_status'] = endpoint_check
            
            if not endpoint_check['passed']:
                verification_results['status'] = 'failed'
                return verification_results
            
            # Performance tests
            performance_check = await self._check_performance(endpoint_name)
            verification_results['checks']['performance'] = performance_check
            
            # Healthcare compliance tests
            compliance_check = await self._check_healthcare_compliance(endpoint_name)
            verification_results['checks']['compliance'] = compliance_check
            
            # Cultural sensitivity tests
            sensitivity_check = await self._check_cultural_sensitivity(endpoint_name)
            verification_results['checks']['cultural_sensitivity'] = sensitivity_check
            
            # Monitoring setup verification
            monitoring_check = await self._check_monitoring_setup(endpoint_name)
            verification_results['checks']['monitoring'] = monitoring_check
            
            # Overall status
            all_passed = all(
                check['passed'] 
                for check in verification_results['checks'].values()
            )
            verification_results['status'] = 'passed' if all_passed else 'failed'
            
        except Exception as e:
            logger.error(f"Verification failed: {e}")
            verification_results['status'] = 'error'
            verification_results['error'] = str(e)
        
        return verification_results    
    async def _check_endpoint_status(self, endpoint_name: str) -> Dict[str, Any]:
        """Check if endpoint is in service."""
        try:
            response = self.sagemaker_client.describe_endpoint(
                EndpointName=endpoint_name
            )
            
            status = response['EndpointStatus']
            in_service = status == 'InService'
            
            return {
                'passed': in_service,
                'status': status,
                'message': f"Endpoint status: {status}",
                'creation_time': response['CreationTime'].isoformat(),
                'last_modified': response['LastModifiedTime'].isoformat()
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'message': 'Failed to check endpoint status'
            }
    
    async def _check_performance(self, endpoint_name: str) -> Dict[str, Any]:
        """Run performance tests on the endpoint."""
        test_samples = [
            {
                'text': 'The doctor will see you now for your appointment.',
                'source_language': 'en',
                'target_language': 'ar',
                'cultural_region': 'middle_east'
            },
            {
                'text': 'Please take this medication twice daily with food.',
                'source_language': 'en',
                'target_language': 'es',
                'cultural_region': 'latin_america'
            },
            {
                'text': 'We need to discuss your treatment options with your family.',
                'source_language': 'en',
                'target_language': 'so',
                'cultural_region': 'east_africa'
            }
        ]
        
        latencies = []
        errors = 0
        
        for sample in test_samples * 10:  # Run 30 tests
            start_time = time.time()
            
            try:
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Accept='application/json',
                    Body=json.dumps(sample)
                )
                
                result = json.loads(response['Body'].read().decode())
                latency = (time.time() - start_time) * 1000  # Convert to ms
                latencies.append(latency)
                
                # Validate response structure
                required_fields = ['detected_patterns', 'cultural_sensitivity_score']
                if not all(field in result for field in required_fields):
                    errors += 1
                    
            except Exception as e:
                logger.error(f"Performance test error: {e}")
                errors += 1
                latencies.append(self.thresholds['latency_ms'] * 2)  # Penalty
        
        avg_latency = sum(latencies) / len(latencies) if latencies else 999999
        error_rate = errors / len(test_samples * 10)
        
        return {
            'passed': (
                avg_latency <= self.thresholds['latency_ms'] and
                error_rate <= self.thresholds['error_rate']
            ),
            'metrics': {
                'average_latency_ms': avg_latency,
                'min_latency_ms': min(latencies) if latencies else 0,
                'max_latency_ms': max(latencies) if latencies else 0,
                'error_rate': error_rate,
                'total_tests': len(test_samples * 10)
            },
            'message': f"Avg latency: {avg_latency:.1f}ms, Error rate: {error_rate:.2%}"
        }    
    async def _check_healthcare_compliance(self, endpoint_name: str) -> Dict[str, Any]:
        """Verify healthcare-specific compliance requirements."""
        compliance_tests = []
        
        # Test 1: PHI handling
        phi_test = {
            'text': 'Patient John Doe, DOB 01/15/1980, needs insulin for diabetes.',
            'source_language': 'en',
            'target_language': 'ar',
            'cultural_region': 'middle_east'
        }
        
        try:
            response = self.sagemaker_runtime.invoke_endpoint(
                EndpointName=endpoint_name,
                ContentType='application/json',
                Accept='application/json',
                Body=json.dumps(phi_test)
            )
            
            result = json.loads(response['Body'].read().decode())
            
            # Verify no PHI in response
            phi_handled = not any(
                term in str(result).lower() 
                for term in ['john doe', '01/15/1980', 'doe']
            )
            
            compliance_tests.append({
                'test': 'PHI_handling',
                'passed': phi_handled,
                'message': 'PHI properly anonymized' if phi_handled else 'PHI exposed'
            })
            
        except Exception as e:
            compliance_tests.append({
                'test': 'PHI_handling',
                'passed': False,
                'error': str(e)
            })
        
        # Test 2: Critical medical terms
        medical_tests = [
            {
                'text': 'Patient is allergic to penicillin and requires alternative antibiotics.',
                'critical_info': 'allergy'
            },
            {
                'text': 'Emergency: Patient experiencing chest pain and shortness of breath.',
                'critical_info': 'emergency'
            },
            {
                'text': 'Do not eat or drink anything before the surgery tomorrow.',
                'critical_info': 'pre-surgery'
            }
        ]
        
        for test in medical_tests:
            try:
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Accept='application/json',
                    Body=json.dumps({
                        'text': test['text'],
                        'source_language': 'en',
                        'target_language': 'ar',
                        'cultural_region': 'middle_east'
                    })
                )
                
                result = json.loads(response['Body'].read().decode())
                
                # Check if critical patterns detected
                critical_detected = any(
                    pattern in result.get('detected_patterns', [])
                    for pattern in ['authority_deference', 'formal']
                )
                
                compliance_tests.append({
                    'test': f'critical_info_{test["critical_info"]}',
                    'passed': critical_detected,
                    'message': f'Critical info handling for {test["critical_info"]}'
                })
                
            except Exception as e:
                compliance_tests.append({
                    'test': f'critical_info_{test["critical_info"]}',
                    'passed': False,
                    'error': str(e)
                })
        
        all_passed = all(test['passed'] for test in compliance_tests)
        
        return {
            'passed': all_passed,
            'tests': compliance_tests,
            'message': f'{sum(t["passed"] for t in compliance_tests)}/{len(compliance_tests)} compliance tests passed'
        }    
    async def _check_cultural_sensitivity(self, endpoint_name: str) -> Dict[str, Any]:
        """Test cultural sensitivity accuracy."""
        cultural_tests = [
            {
                'region': 'middle_east',
                'text': 'Inshallah, your mother will recover soon.',
                'expected_patterns': ['religious_references', 'family_involvement']
            },
            {
                'region': 'south_asia',
                'text': 'Please ask your husband to come for the consultation.',
                'expected_patterns': ['gender_specific', 'family_involvement']
            },
            {
                'region': 'east_africa',
                'text': 'The elders in your community should be informed.',
                'expected_patterns': ['age_respectful', 'family_involvement']
            }
        ]
        
        sensitivity_scores = []
        pattern_accuracy = []
        
        for test in cultural_tests:
            try:
                response = self.sagemaker_runtime.invoke_endpoint(
                    EndpointName=endpoint_name,
                    ContentType='application/json',
                    Accept='application/json',
                    Body=json.dumps({
                        'text': test['text'],
                        'source_language': 'en',
                        'target_language': 'ar',
                        'cultural_region': test['region']
                    })
                )
                
                result = json.loads(response['Body'].read().decode())
                
                # Check cultural sensitivity score
                sensitivity_score = result.get('cultural_sensitivity_score', 0)
                sensitivity_scores.append(sensitivity_score)
                
                # Check pattern detection accuracy
                detected_patterns = result.get('detected_patterns', [])
                correct_patterns = sum(
                    1 for pattern in test['expected_patterns']
                    if pattern in detected_patterns
                )
                accuracy = correct_patterns / len(test['expected_patterns'])
                pattern_accuracy.append(accuracy)
                
            except Exception as e:
                logger.error(f"Cultural sensitivity test error: {e}")
                sensitivity_scores.append(0)
                pattern_accuracy.append(0)
        
        avg_sensitivity = sum(sensitivity_scores) / len(sensitivity_scores)
        avg_accuracy = sum(pattern_accuracy) / len(pattern_accuracy)
        
        return {
            'passed': avg_sensitivity >= self.thresholds['cultural_sensitivity'],
            'metrics': {
                'average_sensitivity_score': avg_sensitivity,
                'pattern_detection_accuracy': avg_accuracy,
                'tests_run': len(cultural_tests)
            },
            'message': f'Avg sensitivity: {avg_sensitivity:.3f}, Pattern accuracy: {avg_accuracy:.2%}'
        }
    
    async def _check_monitoring_setup(self, endpoint_name: str) -> Dict[str, Any]:
        """Verify monitoring is properly configured."""
        try:
            # Check CloudWatch alarms
            alarms_response = self.cloudwatch.describe_alarms(
                AlarmNamePrefix=endpoint_name
            )
            
            alarms = alarms_response.get('MetricAlarms', [])
            
            # Required alarms for healthcare
            required_alarms = ['ModelLatency', 'Invocation4XXErrors']
            existing_alarms = [alarm['AlarmName'] for alarm in alarms]
            
            missing_alarms = [
                alarm for alarm in required_alarms
                if not any(alarm in existing for existing in existing_alarms)
            ]
            
            # Check data capture configuration
            endpoint_config = self.sagemaker_client.describe_endpoint_config(
                EndpointConfigName=f"{endpoint_name}-config"
            )
            
            data_capture_enabled = False
            if 'DataCaptureConfig' in endpoint_config:
                data_capture_enabled = endpoint_config['DataCaptureConfig'].get(
                    'EnableCapture', False
                )
            
            monitoring_passed = (
                len(missing_alarms) == 0 and 
                data_capture_enabled
            )
            
            return {
                'passed': monitoring_passed,
                'details': {
                    'alarms_configured': len(alarms),
                    'missing_alarms': missing_alarms,
                    'data_capture_enabled': data_capture_enabled
                },
                'message': 'Monitoring properly configured' if monitoring_passed else 'Monitoring issues found'
            }
            
        except Exception as e:
            return {
                'passed': False,
                'error': str(e),
                'message': 'Failed to check monitoring setup'
            }
    
    async def verify_all_endpoints(self) -> Dict[str, Any]:
        """Verify all cultural adaptation endpoints."""
        # List all endpoints
        endpoints_response = self.sagemaker_client.list_endpoints(
            StatusEquals='InService',
            NameContains='cultural'
        )
        
        endpoints = endpoints_response.get('Endpoints', [])
        
        if not endpoints:
            logger.warning("No cultural adaptation endpoints found")
            return {
                'status': 'warning',
                'message': 'No endpoints found',
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Verify each endpoint
        verification_results = {
            'timestamp': datetime.utcnow().isoformat(),
            'endpoints': {},
            'summary': {
                'total': len(endpoints),
                'passed': 0,
                'failed': 0
            }
        }
        
        for endpoint in endpoints:
            endpoint_name = endpoint['EndpointName']
            result = await self.verify_deployment(endpoint_name)
            
            verification_results['endpoints'][endpoint_name] = result
            
            if result['status'] == 'passed':
                verification_results['summary']['passed'] += 1
            else:
                verification_results['summary']['failed'] += 1
        
        # Overall status
        verification_results['status'] = (
            'passed' if verification_results['summary']['failed'] == 0 else 'failed'
        )
        
        return verification_results


async def main():
    """Main verification function."""
    parser = argparse.ArgumentParser(
        description='Verify SageMaker deployments for Haven Health Passport'
    )
    
    parser.add_argument(
        '--endpoint',
        help='Specific endpoint to verify (optional)'
    )
    
    parser.add_argument(
        '--region',
        default='us-east-1',
        help='AWS region'
    )
    
    parser.add_argument(
        '--output',
        default='deployment_verification_report.json',
        help='Output file for verification report'
    )
    
    args = parser.parse_args()
    
    # Initialize verifier
    verifier = SageMakerDeploymentVerifier(region=args.region)
    
    # Run verification
    if args.endpoint:
        logger.info(f"Verifying specific endpoint: {args.endpoint}")
        results = await verifier.verify_deployment(args.endpoint)
    else:
        logger.info("Verifying all cultural adaptation endpoints")
        results = await verifier.verify_all_endpoints()
    
    # Save results
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Print summary
    logger.info(f"Verification complete. Status: {results['status']}")
    
    if 'summary' in results:
        logger.info(
            f"Endpoints verified: {results['summary']['total']} "
            f"(Passed: {results['summary']['passed']}, "
            f"Failed: {results['summary']['failed']})"
        )
    
    # Exit with appropriate code
    exit(0 if results['status'] == 'passed' else 1)


if __name__ == '__main__':
    asyncio.run(main())