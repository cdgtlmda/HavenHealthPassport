#!/usr/bin/env python3
"""
Script to check and document Bedrock model access status.
This helps with the first checklist item: Enable Amazon Bedrock in AWS account
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set

import boto3


# Load AWS credentials from .env.aws file
def load_aws_credentials():
    """Load AWS credentials from .env.aws file."""
    env_file = Path(__file__).parent.parent.parent / ".env.aws"
    if env_file.exists():
        with open(env_file, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
        print("✅ Loaded AWS credentials from .env.aws")
    else:
        print("⚠️  .env.aws file not found")


# Load credentials before importing boto3 clients
load_aws_credentials()

# Models we want to request access for
REQUIRED_MODELS = [
    "anthropic.claude-v2",
    "anthropic.claude-v2:1",
    "anthropic.claude-instant-v1",
    "anthropic.claude-3-sonnet-20240229-v1:0",
    "anthropic.claude-3-haiku-20240307-v1:0",
    "amazon.titan-text-express-v1",
    "amazon.titan-text-lite-v1",
    "amazon.titan-embed-text-v1",
    "meta.llama2-70b-chat-v1",
    "meta.llama2-13b-chat-v1",
    "ai21.j2-ultra-v1",
    "ai21.j2-mid-v1",
]


def check_bedrock_availability(region: str) -> bool:
    """Check if Bedrock is available in the specified region."""
    try:
        client = boto3.client("bedrock", region_name=region)
        client.list_foundation_models(maxResults=1)
        return True
    except Exception as e:
        if "UnknownService" in str(e):
            return False
        return True


def get_available_models(region: str) -> List[Dict]:
    """Get list of available foundation models in the region."""
    try:
        client = boto3.client("bedrock", region_name=region)
        response = client.list_foundation_models()
        return response.get("modelSummaries", [])
    except Exception as e:
        error_msg = str(e)
        if (
            "UnrecognizedClientException" in error_msg
            or "InvalidUserToken" in error_msg
        ):
            print(f"⚠️  AWS Authentication Error in {region}")
            print("   Please configure valid AWS credentials")
        elif "AccessDeniedException" in error_msg:
            print(f"⚠️  Access Denied in {region}")
            print("   Your AWS account may not have Bedrock permissions")
        else:
            print(f"Error listing models in {region}: {e}")
        return []


def check_model_access_status(region: str) -> Dict[str, Set[str]]:
    """Check which models are available vs which need to be requested."""
    available_models = get_available_models(region)
    available_model_ids = {model["modelId"] for model in available_models}

    # Models that are available
    accessible_models = set(REQUIRED_MODELS) & available_model_ids

    # Models that need to be requested
    models_to_request = set(REQUIRED_MODELS) - available_model_ids

    return {
        "accessible": accessible_models,
        "to_request": models_to_request,
        "all_available": available_model_ids,
    }


def generate_report(regions: List[str]):
    """Generate a comprehensive report of Bedrock access status."""
    print("=" * 80)
    print("AMAZON BEDROCK ACCESS STATUS REPORT")
    print("=" * 80)
    print(f"Generated at: {datetime.now().isoformat()}")
    print()

    for region in regions:
        print(f"\nRegion: {region}")
        print("-" * 40)

        if not check_bedrock_availability(region):
            print("❌ Bedrock is NOT available in this region")
            continue

        print("✅ Bedrock is available in this region")

        status = check_model_access_status(region)

        print(f"\nModels with access granted: {len(status['accessible'])}")
        for model in sorted(status["accessible"]):
            print(f"  ✅ {model}")

        print(f"\nModels requiring access request: {len(status['to_request'])}")
        for model in sorted(status["to_request"]):
            print(f"  ⏳ {model}")

        print(f"\nTotal models available in region: {len(status['all_available'])}")


def print_access_instructions():
    """Print instructions for requesting model access."""
    print("\n" + "=" * 80)
    print("HOW TO REQUEST MODEL ACCESS")
    print("=" * 80)
    print(
        """
1. Sign in to AWS Console
2. Navigate to Amazon Bedrock service
3. Click on "Model access" in the left navigation
4. Click "Manage model access" button
5. Select the models listed above as "requiring access request"
6. Submit the request
7. Most models are approved instantly

Note: Some models may require additional information or have regional restrictions.
"""
    )


def main():
    """Main execution function."""
    import argparse
    from pathlib import Path
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Check Amazon Bedrock access status")
    parser.add_argument("regions", nargs="*", default=["us-east-1", "us-west-2", "eu-west-1"],
                       help="AWS regions to check (default: us-east-1, us-west-2, eu-west-1)")
    parser.add_argument("--output-dir", "-o", type=str, default="./bedrock_tests",
                       help="Output directory for reports (default: ./bedrock_tests)")
    parser.add_argument("--format", "-f", choices=["txt", "json", "csv", "all"], default="all",
                       help="Output format (default: all)")
    parser.add_argument("--no-save", action="store_true",
                       help="Don't save report to file")
    args = parser.parse_args()

    try:
        # Collect report data
        report_data = collect_report_data(args.regions)
        
        # Generate and print report
        generate_report(args.regions)
        print_access_instructions()

        # Save report to file(s)
        if not args.no_save:
            save_test_results(report_data, Path(args.output_dir), args.format)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

def collect_report_data(regions: List[str]) -> Dict[str, Any]:
    """Collect comprehensive report data for all regions."""
    report_data = {
        "test_metadata": {
            "timestamp": datetime.utcnow().isoformat(),
            "aws_account": boto3.client("sts").get_caller_identity()["Account"],
            "test_version": "1.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "regions_tested": regions
        },
        "regional_results": {},
        "summary": {
            "total_regions_tested": len(regions),
            "regions_with_bedrock": 0,
            "total_models_accessible": 0,
            "total_models_to_request": 0,
            "model_performance": {}
        }
    }
    
    for region in regions:
        print(f"\nTesting region: {region}...")
        
        # Check if Bedrock is available
        available = check_bedrock_availability(region)
        
        if available:
            report_data["summary"]["regions_with_bedrock"] += 1
            
            # Get model access status
            status = check_model_access_status(region)
            
            # Test model performance for accessible models
            performance_data = {}
            if status["accessible"]:
                print(f"Testing {len(status['accessible'])} accessible models...")
                performance_data = test_model_performance(region, status["accessible"])
            
            report_data["regional_results"][region] = {
                "bedrock_available": True,
                "accessible_models": status["accessible"],
                "models_to_request": status["to_request"],
                "all_available_models": status["all_available"],
                "performance_tests": performance_data,
                "test_timestamp": datetime.utcnow().isoformat()
            }
            
            # Update summary
            report_data["summary"]["total_models_accessible"] += len(status["accessible"])
            report_data["summary"]["total_models_to_request"] += len(status["to_request"])
            
            # Aggregate performance data
            for model_id, perf in performance_data.items():
                if model_id not in report_data["summary"]["model_performance"]:
                    report_data["summary"]["model_performance"][model_id] = {
                        "regions_tested": [],
                        "avg_response_time": [],
                        "success_rate": []
                    }
                
                report_data["summary"]["model_performance"][model_id]["regions_tested"].append(region)
                if perf.get("success"):
                    report_data["summary"]["model_performance"][model_id]["avg_response_time"].append(
                        perf.get("response_time", 0)
                    )
                    report_data["summary"]["model_performance"][model_id]["success_rate"].append(1.0)
                else:
                    report_data["summary"]["model_performance"][model_id]["success_rate"].append(0.0)
        else:
            report_data["regional_results"][region] = {
                "bedrock_available": False,
                "accessible_models": [],
                "models_to_request": [],
                "all_available_models": [],
                "performance_tests": {},
                "test_timestamp": datetime.utcnow().isoformat()
            }
    
    # Calculate average performance metrics
    for model_id, metrics in report_data["summary"]["model_performance"].items():
        if metrics["avg_response_time"]:
            metrics["avg_response_time"] = sum(metrics["avg_response_time"]) / len(metrics["avg_response_time"])
        else:
            metrics["avg_response_time"] = None
        
        metrics["success_rate"] = sum(metrics["success_rate"]) / len(metrics["success_rate"])
    
    return report_data


def test_model_performance(region: str, model_ids: List[str]) -> Dict[str, Any]:
    """Test performance of accessible models."""
    bedrock = boto3.client("bedrock-runtime", region_name=region)
    performance_data = {}
    
    test_prompt = "Hello, this is a test message. Please respond with a brief greeting."
    
    for model_id in model_ids[:5]:  # Test up to 5 models to avoid excessive API calls
        try:
            start_time = time.time()
            
            # Prepare request based on model type
            if "claude" in model_id:
                body = json.dumps({
                    "messages": [{"role": "user", "content": test_prompt}],
                    "max_tokens": 100,
                    "anthropic_version": "bedrock-2023-05-31"
                })
            elif "titan" in model_id:
                body = json.dumps({
                    "inputText": test_prompt,
                    "textGenerationConfig": {"maxTokenCount": 100}
                })
            else:
                # Generic format
                body = json.dumps({"prompt": test_prompt, "max_tokens": 100})
            
            response = bedrock.invoke_model(
                modelId=model_id,
                body=body,
                contentType="application/json"
            )
            
            response_time = time.time() - start_time
            
            performance_data[model_id] = {
                "success": True,
                "response_time": response_time,
                "response_size": len(response["body"].read()),
                "test_timestamp": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            performance_data[model_id] = {
                "success": False,
                "error": str(e),
                "test_timestamp": datetime.utcnow().isoformat()
            }
    
    return performance_data


def save_test_results(results: Dict[str, Any], output_dir: Path, format: str = "all") -> None:
    """Save test results in multiple formats."""
    output_dir.mkdir(exist_ok=True, parents=True)
    
    # Create timestamped filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    base_filename = f'bedrock_test_{timestamp}'
    
    formats_to_save = ["txt", "json", "csv"] if format == "all" else [format]
    
    for fmt in formats_to_save:
        if fmt == "json":
            save_json_report(results, output_dir / f"{base_filename}.json")
        elif fmt == "txt":
            save_text_report(results, output_dir / f"{base_filename}.txt")
        elif fmt == "csv":
            save_csv_report(results, output_dir / f"{base_filename}.csv")
    
    # Generate summary report
    generate_summary_report(results, output_dir / f"{base_filename}_summary.md")
    
    print(f"\nReports saved to: {output_dir}")
    print(f"- JSON: {base_filename}.json")
    print(f"- Text: {base_filename}.txt")
    print(f"- CSV: {base_filename}.csv")
    print(f"- Summary: {base_filename}_summary.md")


def save_json_report(results: Dict[str, Any], filepath: Path) -> None:
    """Save results as JSON."""
    with open(filepath, 'w') as f:
        json.dump(results, f, indent=2, default=str)


def save_text_report(results: Dict[str, Any], filepath: Path) -> None:
    """Save results as formatted text report."""
    with open(filepath, 'w') as f:
        f.write("=" * 80 + "\n")
        f.write("AMAZON BEDROCK ACCESS STATUS REPORT\n")
        f.write("=" * 80 + "\n")
        f.write(f"Generated at: {results['test_metadata']['timestamp']}\n")
        f.write(f"AWS Account: {results['test_metadata']['aws_account']}\n")
        f.write(f"Regions Tested: {', '.join(results['test_metadata']['regions_tested'])}\n")
        f.write("\n")
        
        # Summary
        f.write("SUMMARY\n")
        f.write("-" * 40 + "\n")
        summary = results['summary']
        f.write(f"Regions with Bedrock: {summary['regions_with_bedrock']}/{summary['total_regions_tested']}\n")
        f.write(f"Total Accessible Models: {summary['total_models_accessible']}\n")
        f.write(f"Total Models Requiring Access: {summary['total_models_to_request']}\n")
        f.write("\n")
        
        # Regional Details
        for region, data in results['regional_results'].items():
            f.write(f"\nREGION: {region}\n")
            f.write("-" * 40 + "\n")
            
            if data['bedrock_available']:
                f.write("✅ Bedrock is available\n\n")
                
                f.write(f"Accessible Models ({len(data['accessible_models'])}):\n")
                for model in sorted(data['accessible_models']):
                    f.write(f"  ✅ {model}\n")
                
                f.write(f"\nModels Requiring Access ({len(data['models_to_request'])}):\n")
                for model in sorted(data['models_to_request']):
                    f.write(f"  ⏳ {model}\n")
                
                if data['performance_tests']:
                    f.write("\nPerformance Test Results:\n")
                    for model_id, perf in data['performance_tests'].items():
                        if perf['success']:
                            f.write(f"  {model_id}: {perf['response_time']:.2f}s response time\n")
                        else:
                            f.write(f"  {model_id}: ❌ Failed - {perf.get('error', 'Unknown error')}\n")
            else:
                f.write("❌ Bedrock is NOT available\n")


def save_csv_report(results: Dict[str, Any], filepath: Path) -> None:
    """Save results as CSV."""
    import csv
    
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Header
        writer.writerow([
            "Region", "Bedrock Available", "Model ID", "Access Status", 
            "Performance Tested", "Response Time (s)", "Test Result"
        ])
        
        # Data rows
        for region, data in results['regional_results'].items():
            if not data['bedrock_available']:
                writer.writerow([region, "No", "", "", "", "", ""])
                continue
            
            # Write accessible models
            for model in data['accessible_models']:
                perf = data['performance_tests'].get(model, {})
                writer.writerow([
                    region,
                    "Yes",
                    model,
                    "Accessible",
                    "Yes" if model in data['performance_tests'] else "No",
                    f"{perf.get('response_time', ''):.2f}" if perf.get('success') else "",
                    "Success" if perf.get('success') else perf.get('error', '')
                ])
            
            # Write models requiring access
            for model in data['models_to_request']:
                writer.writerow([
                    region,
                    "Yes",
                    model,
                    "Requires Access",
                    "No",
                    "",
                    ""
                ])


def generate_summary_report(results: Dict[str, Any], filepath: Path) -> None:
    """Generate a markdown summary report."""
    with open(filepath, 'w') as f:
        f.write("# Amazon Bedrock Access Test Summary\n\n")
        f.write(f"**Generated:** {results['test_metadata']['timestamp']}\n")
        f.write(f"**AWS Account:** {results['test_metadata']['aws_account']}\n\n")
        
        f.write("## Overview\n\n")
        summary = results['summary']
        f.write(f"- **Regions Tested:** {summary['total_regions_tested']}\n")
        f.write(f"- **Regions with Bedrock:** {summary['regions_with_bedrock']}\n")
        f.write(f"- **Total Accessible Models:** {summary['total_models_accessible']}\n")
        f.write(f"- **Models Requiring Access:** {summary['total_models_to_request']}\n\n")
        
        if summary['model_performance']:
            f.write("## Model Performance Summary\n\n")
            f.write("| Model | Regions Tested | Avg Response Time | Success Rate |\n")
            f.write("|-------|----------------|-------------------|-------------|\n")
            
            for model_id, metrics in summary['model_performance'].items():
                avg_time = metrics['avg_response_time']
                time_str = f"{avg_time:.2f}s" if avg_time else "N/A"
                f.write(f"| {model_id} | {len(metrics['regions_tested'])} | {time_str} | {metrics['success_rate']*100:.0f}% |\n")
        
        f.write("\n## Regional Details\n\n")
        for region, data in results['regional_results'].items():
            f.write(f"### {region}\n\n")
            if data['bedrock_available']:
                f.write(f"- ✅ Bedrock Available\n")
                f.write(f"- 🔓 Accessible Models: {len(data['accessible_models'])}\n")
                f.write(f"- 🔒 Requires Access: {len(data['models_to_request'])}\n\n")
            else:
                f.write("- ❌ Bedrock Not Available\n\n")
        
        f.write("## Next Steps\n\n")
        if summary['total_models_to_request'] > 0:
            f.write("1. Request access to additional models through the AWS Console\n")
            f.write("2. Navigate to Amazon Bedrock > Model access\n")
            f.write("3. Click 'Manage model access' and select desired models\n")
            f.write("4. Most models are approved instantly\n")


def generate_performance_trends(output_dir: Path) -> None:
    """Generate performance trend analysis from historical test results."""
    import glob
    
    # Find all JSON test results
    json_files = sorted(glob.glob(str(output_dir / "bedrock_test_*.json")))
    
    if len(json_files) < 2:
        return
    
    trends = {}
    
    for json_file in json_files:
        with open(json_file, 'r') as f:
            data = json.load(f)
            
        timestamp = data['test_metadata']['timestamp']
        
        for model_id, metrics in data['summary']['model_performance'].items():
            if model_id not in trends:
                trends[model_id] = {
                    'timestamps': [],
                    'response_times': [],
                    'success_rates': []
                }
            
            trends[model_id]['timestamps'].append(timestamp)
            trends[model_id]['response_times'].append(metrics.get('avg_response_time', 0))
            trends[model_id]['success_rates'].append(metrics.get('success_rate', 0))
    
    # Save trends report
    with open(output_dir / "performance_trends.json", 'w') as f:
        json.dump(trends, f, indent=2)
