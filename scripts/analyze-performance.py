"""
Performance Analysis Script for Haven Health Passport
Analyzes performance test results and generates actionable insights
"""

import json
import statistics
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Tuple
import matplotlib.pyplot as plt
import seaborn as sns
from dataclasses import dataclass
import warnings
warnings.filterwarnings('ignore')


@dataclass
class PerformanceMetrics:
    """Performance test metrics"""
    timestamp: datetime
    endpoint: str
    response_time: float
    status_code: int
    success: bool
    concurrent_users: int
    scenario: str
    error_message: Optional[str] = None


class PerformanceAnalyzer:
    """Analyzes performance test results"""
    
    def __init__(self, results_file: str, threshold_p95: float = 500):
        self.results_file = results_file
        self.threshold_p95 = threshold_p95
        self.metrics: List[PerformanceMetrics] = []
        self.analysis_results = {}
        
    def load_results(self):
        """Load performance test results"""
        with open(self.results_file, 'r') as f:
            raw_data = json.load(f)
        
        # Convert to metrics objects
        for entry in raw_data:
            self.metrics.append(PerformanceMetrics(
                timestamp=datetime.fromisoformat(entry['timestamp']),
                endpoint=entry['endpoint'],
                response_time=entry['response_time'],
                status_code=entry['status_code'],
                success=entry['status_code'] < 400,
                concurrent_users=entry.get('concurrent_users', 1),
                scenario=entry.get('scenario', 'default'),
                error_message=entry.get('error_message')
            ))
    
    def analyze(self):
        """Run comprehensive performance analysis"""
        print("Running Performance Analysis")
        print("=" * 50)
        
        # Basic statistics
        self.calculate_basic_statistics()
        
        # Response time analysis
        self.analyze_response_times()
        
        # Error analysis
        self.analyze_errors()
        
        # Throughput analysis
        self.analyze_throughput()
        
        # Scalability analysis
        self.analyze_scalability()
        
        # Endpoint-specific analysis
        self.analyze_endpoints()
        
        # Generate visualizations
        self.generate_visualizations()
        
        return self.analysis_results
    
    def calculate_basic_statistics(self):
        """Calculate basic performance statistics"""
        response_times = [m.response_time for m in self.metrics if m.success]
        
        if not response_times:
            print("No successful requests to analyze")
            return
        
        self.analysis_results['basic_stats'] = {
            'total_requests': len(self.metrics),
            'successful_requests': len(response_times),
            'failed_requests': len(self.metrics) - len(response_times),
            'success_rate': len(response_times) / len(self.metrics) * 100,
            'mean_response_time': statistics.mean(response_times),
            'median_response_time': statistics.median(response_times),
            'std_dev': statistics.stdev(response_times) if len(response_times) > 1 else 0,
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'p50': np.percentile(response_times, 50),
            'p75': np.percentile(response_times, 75),
            'p90': np.percentile(response_times, 90),
            'p95': np.percentile(response_times, 95),
            'p99': np.percentile(response_times, 99)
        }
        
        print("\nBasic Statistics:")
        for key, value in self.analysis_results['basic_stats'].items():
            if 'time' in key:
                print(f"  {key}: {value:.2f}ms")
            elif 'rate' in key:
                print(f"  {key}: {value:.2f}%")
            else:
                print(f"  {key}: {value}")
    
    def analyze_response_times(self):
        """Analyze response time patterns"""
        df = pd.DataFrame([vars(m) for m in self.metrics])
        
        # Response time distribution
        response_dist = {
            'under_100ms': len(df[df['response_time'] < 100]),
            '100_to_500ms': len(df[(df['response_time'] >= 100) & (df['response_time'] < 500)]),
            '500ms_to_1s': len(df[(df['response_time'] >= 500) & (df['response_time'] < 1000)]),
            '1s_to_5s': len(df[(df['response_time'] >= 1000) & (df['response_time'] < 5000)]),
            'over_5s': len(df[df['response_time'] >= 5000])
        }
        
        # Time-based analysis
        df['hour'] = df['timestamp'].dt.hour
        hourly_avg = df.groupby('hour')['response_time'].mean()
        
        # Identify performance degradation
        df['time_window'] = pd.cut(df.index, bins=10)
        window_stats = df.groupby('time_window')['response_time'].agg(['mean', 'std', 'count'])
        
        # Check for increasing trend
        response_times_series = df['response_time'].rolling(window=100).mean()
        trend = np.polyfit(range(len(response_times_series.dropna())), 
                          response_times_series.dropna(), 1)[0]
        
        self.analysis_results['response_time_analysis'] = {
            'distribution': response_dist,
            'hourly_average': hourly_avg.to_dict(),
            'performance_trend': 'degrading' if trend > 0.1 else 'stable',
            'trend_coefficient': trend
        }
        
        print("\nResponse Time Analysis:")
        print("  Distribution:")
        for range_name, count in response_dist.items():
            percentage = count / len(df) * 100
            print(f"    {range_name}: {count} ({percentage:.1f}%)")
        print(f"  Performance Trend: {self.analysis_results['response_time_analysis']['performance_trend']}")
    
    def analyze_errors(self):
        """Analyze error patterns"""
        errors = [m for m in self.metrics if not m.success]
        
        if not errors:
            self.analysis_results['error_analysis'] = {'error_rate': 0}
            return
        
        # Error categorization
        error_by_code = {}
        error_by_endpoint = {}
        error_timeline = {}
        
        for error in errors:
            # By status code
            code = str(error.status_code)
            error_by_code[code] = error_by_code.get(code, 0) + 1
            
            # By endpoint
            endpoint = error.endpoint
            error_by_endpoint[endpoint] = error_by_endpoint.get(endpoint, 0) + 1
            
            # Timeline (5-minute buckets)
            bucket = error.timestamp.replace(minute=error.timestamp.minute // 5 * 5, 
                                           second=0, microsecond=0)
            error_timeline[bucket.isoformat()] = error_timeline.get(bucket.isoformat(), 0) + 1
        
        # Identify error spikes
        if error_timeline:
            avg_errors = statistics.mean(error_timeline.values())
            error_spikes = [time for time, count in error_timeline.items() 
                          if count > avg_errors * 2]
        else:
            error_spikes = []
        
        self.analysis_results['error_analysis'] = {
            'error_rate': len(errors) / len(self.metrics) * 100,
            'total_errors': len(errors),
            'errors_by_code': error_by_code,
            'errors_by_endpoint': error_by_endpoint,
            'error_spikes': error_spikes,
            'most_common_error': max(error_by_code.items(), key=lambda x: x[1])[0] if error_by_code else None
        }
        
        print("\nError Analysis:")
        print(f"  Error Rate: {self.analysis_results['error_analysis']['error_rate']:.2f}%")
        print("  Errors by Status Code:")
        for code, count in sorted(error_by_code.items()):
            print(f"    {code}: {count}")
    
    def analyze_throughput(self):
        """Analyze system throughput"""
        df = pd.DataFrame([vars(m) for m in self.metrics])
        
        # Calculate requests per second
        df['second'] = df['timestamp'].dt.floor('S')
        rps = df.groupby('second').size()
        
        # Calculate successful requests per second
        success_df = df[df['success']]
        success_rps = success_df.groupby('second').size()
        
        # Throughput by concurrent users
        throughput_by_users = df.groupby('concurrent_users').apply(
            lambda x: len(x) / ((x['timestamp'].max() - x['timestamp'].min()).total_seconds() + 1)
        )
        
        self.analysis_results['throughput_analysis'] = {
            'avg_rps': rps.mean(),
            'max_rps': rps.max(),
            'min_rps': rps.min(),
            'avg_success_rps': success_rps.mean() if len(success_rps) > 0 else 0,
            'throughput_by_concurrent_users': throughput_by_users.to_dict()
        }
        
        print("\nThroughput Analysis:")
        print(f"  Average RPS: {self.analysis_results['throughput_analysis']['avg_rps']:.2f}")
        print(f"  Max RPS: {self.analysis_results['throughput_analysis']['max_rps']}")
        print(f"  Success RPS: {self.analysis_results['throughput_analysis']['avg_success_rps']:.2f}")
    
    def analyze_scalability(self):
        """Analyze system scalability characteristics"""
        df = pd.DataFrame([vars(m) for m in self.metrics])
        
        # Group by concurrent users
        scalability_metrics = df.groupby('concurrent_users').agg({
            'response_time': ['mean', 'median', lambda x: np.percentile(x, 95)],
            'success': 'mean'
        })
        
        scalability_metrics.columns = ['mean_response_time', 'median_response_time', 
                                      'p95_response_time', 'success_rate']
        
        # Calculate scaling efficiency
        baseline_users = scalability_metrics.index.min()
        baseline_throughput = len(df[df['concurrent_users'] == baseline_users])
        
        scaling_efficiency = {}
        for users in scalability_metrics.index:
            if users > baseline_users:
                actual_throughput = len(df[df['concurrent_users'] == users])
                expected_throughput = baseline_throughput * (users / baseline_users)
                efficiency = (actual_throughput / expected_throughput) * 100
                scaling_efficiency[users] = efficiency
        
        # Find breaking point (where success rate < 95% or p95 > threshold)
        breaking_point = None
        for users in sorted(scalability_metrics.index):
            if (scalability_metrics.loc[users, 'success_rate'] < 0.95 or 
                scalability_metrics.loc[users, 'p95_response_time'] > self.threshold_p95):
                breaking_point = users
                break
        
        self.analysis_results['scalability_analysis'] = {
            'metrics_by_users': scalability_metrics.to_dict('index'),
            'scaling_efficiency': scaling_efficiency,
            'breaking_point': breaking_point,
            'max_tested_users': scalability_metrics.index.max()
        }
        
        print("\nScalability Analysis:")
        print("  Performance by Concurrent Users:")
        for users, metrics in scalability_metrics.iterrows():
            print(f"    {users} users: {metrics['mean_response_time']:.0f}ms mean, "
                  f"{metrics['p95_response_time']:.0f}ms p95, "
                  f"{metrics['success_rate']*100:.1f}% success")
        if breaking_point:
            print(f"  Breaking Point: {breaking_point} concurrent users")
    
    def analyze_endpoints(self):
        """Analyze performance by endpoint"""
        df = pd.DataFrame([vars(m) for m in self.metrics])
        
        endpoint_stats = {}
        
        for endpoint in df['endpoint'].unique():
            endpoint_df = df[df['endpoint'] == endpoint]
            successful = endpoint_df[endpoint_df['success']]
            
            if len(successful) > 0:
                stats = {
                    'count': len(endpoint_df),
                    'success_rate': len(successful) / len(endpoint_df) * 100,
                    'mean_response_time': successful['response_time'].mean(),
                    'p95_response_time': successful['response_time'].quantile(0.95),
                    'p99_response_time': successful['response_time'].quantile(0.99),
                    'errors': len(endpoint_df) - len(successful)
                }
            else:
                stats = {
                    'count': len(endpoint_df),
                    'success_rate': 0,
                    'errors': len(endpoint_df)
                }
            
            endpoint_stats[endpoint] = stats
        
        # Identify problematic endpoints
        problematic_endpoints = [
            endpoint for endpoint, stats in endpoint_stats.items()
            if stats.get('p95_response_time', 0) > self.threshold_p95 or 
               stats['success_rate'] < 95
        ]
        
        self.analysis_results['endpoint_analysis'] = {
            'endpoint_stats': endpoint_stats,
            'problematic_endpoints': problematic_endpoints,
            'slowest_endpoint': max(endpoint_stats.items(), 
                                   key=lambda x: x[1].get('p95_response_time', 0))[0]
        }
        
        print("\nEndpoint Analysis:")
        print("  Top 5 Slowest Endpoints (P95):")
        sorted_endpoints = sorted(endpoint_stats.items(), 
                                key=lambda x: x[1].get('p95_response_time', 0), 
                                reverse=True)[:5]
        for endpoint, stats in sorted_endpoints:
            if 'p95_response_time' in stats:
                print(f"    {endpoint}: {stats['p95_response_time']:.0f}ms")
    
    def generate_visualizations(self):
        """Generate performance visualization charts"""
        df = pd.DataFrame([vars(m) for m in self.metrics])
        
        # Create figure with subplots
        fig, axes = plt.subplots(2, 3, figsize=(18, 12))
        fig.suptitle('Haven Health Passport Performance Analysis', fontsize=16)
        
        # 1. Response time distribution
        ax1 = axes[0, 0]
        successful_times = df[df['success']]['response_time']
        ax1.hist(successful_times, bins=50, edgecolor='black', alpha=0.7)
        ax1.axvline(self.threshold_p95, color='red', linestyle='--', 
                   label=f'P95 Threshold ({self.threshold_p95}ms)')
        ax1.set_xlabel('Response Time (ms)')
        ax1.set_ylabel('Frequency')
        ax1.set_title('Response Time Distribution')
        ax1.legend()
        
        # 2. Response time over time
        ax2 = axes[0, 1]
        df_sorted = df.sort_values('timestamp')
        ax2.plot(df_sorted['timestamp'], df_sorted['response_time'].rolling(100).mean(), 
                label='Rolling Average (100 requests)')
        ax2.scatter(df[~df['success']]['timestamp'], df[~df['success']]['response_time'], 
                   color='red', s=10, alpha=0.5, label='Failed Requests')
        ax2.set_xlabel('Time')
        ax2.set_ylabel('Response Time (ms)')
        ax2.set_title('Response Time Over Time')
        ax2.legend()
        ax2.tick_params(axis='x', rotation=45)
        
        # 3. Throughput by concurrent users
        ax3 = axes[0, 2]
        throughput_data = self.analysis_results['throughput_analysis']['throughput_by_concurrent_users']
        if throughput_data:
            users = list(throughput_data.keys())
            throughput = list(throughput_data.values())
            ax3.plot(users, throughput, marker='o')
            ax3.set_xlabel('Concurrent Users')
            ax3.set_ylabel('Requests per Second')
            ax3.set_title('Throughput Scalability')
            ax3.grid(True, alpha=0.3)
        
        # 4. Error rate by time
        ax4 = axes[1, 0]
        df['time_bucket'] = pd.cut(df.index, bins=20)
        error_rate_by_time = df.groupby('time_bucket').apply(
            lambda x: (1 - x['success'].mean()) * 100
        )
        ax4.bar(range(len(error_rate_by_time)), error_rate_by_time.values)
        ax4.set_xlabel('Time Period')
        ax4.set_ylabel('Error Rate (%)')
        ax4.set_title('Error Rate Over Time')
        ax4.set_ylim(0, max(error_rate_by_time.max() * 1.1, 5))
        
        # 5. Endpoint performance comparison
        ax5 = axes[1, 1]
        endpoint_stats = self.analysis_results['endpoint_analysis']['endpoint_stats']
        endpoints = list(endpoint_stats.keys())[:10]  # Top 10
        p95_times = [endpoint_stats[e].get('p95_response_time', 0) for e in endpoints]
        
        bars = ax5.barh(range(len(endpoints)), p95_times)
        ax5.set_yticks(range(len(endpoints)))
        ax5.set_yticklabels([e.split('/')[-1] for e in endpoints])
        ax5.set_xlabel('P95 Response Time (ms)')
        ax5.set_title('Endpoint Performance (P95)')
        ax5.axvline(self.threshold_p95, color='red', linestyle='--', alpha=0.7)
        
        # Color bars based on threshold
        for bar, time in zip(bars, p95_times):
            if time > self.threshold_p95:
                bar.set_color('red')
            else:
                bar.set_color('green')
        
        # 6. Success rate by scenario
        ax6 = axes[1, 2]
        scenario_success = df.groupby('scenario')['success'].mean() * 100
        ax6.bar(scenario_success.index, scenario_success.values)
        ax6.set_xlabel('Scenario')
        ax6.set_ylabel('Success Rate (%)')
        ax6.set_title('Success Rate by Scenario')
        ax6.set_ylim(0, 105)
        ax6.axhline(95, color='green', linestyle='--', alpha=0.7, label='95% Target')
        ax6.legend()
        
        plt.tight_layout()
        plt.savefig('performance_analysis.png', dpi=300, bbox_inches='tight')
        plt.close()
        
        print("\nVisualization saved to: performance_analysis.png")
    
    def generate_report(self, output_file: str = 'performance_report.html'):
        """Generate HTML performance report"""
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Haven Health Passport Performance Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                .header {{ background-color: #f0f0f0; padding: 20px; border-radius: 5px; }}
                .metric {{ margin: 10px 0; }}
                .good {{ color: green; }}
                .bad {{ color: red; }}
                .warning {{ color: orange; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
                .section {{ margin: 30px 0; }}
                .recommendation {{ background-color: #fff3cd; padding: 10px; 
                                 border-left: 4px solid #ffc107; margin: 10px 0; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Haven Health Passport Performance Report</h1>
                <p>Generated: {timestamp}</p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                <div class="metric">Total Requests: {total_requests}</div>
                <div class="metric">Success Rate: <span class="{success_class}">{success_rate:.2f}%</span></div>
                <div class="metric">P95 Response Time: <span class="{p95_class}">{p95:.0f}ms</span></div>
                <div class="metric">Average RPS: {avg_rps:.2f}</div>
            </div>
            
            <div class="section">
                <h2>Performance Metrics</h2>
                <table>
                    <tr>
                        <th>Metric</th>
                        <th>Value</th>
                        <th>Status</th>
                    </tr>
                    {metrics_table}
                </table>
            </div>
            
            <div class="section">
                <h2>Endpoint Performance</h2>
                <table>
                    <tr>
                        <th>Endpoint</th>
                        <th>Requests</th>
                        <th>Success Rate</th>
                        <th>P95 Response Time</th>
                        <th>Status</th>
                    </tr>
                    {endpoints_table}
                </table>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                {recommendations}
            </div>
            
            <div class="section">
                <h2>Visualizations</h2>
                <img src="performance_analysis.png" style="max-width: 100%;">
            </div>
        </body>
        </html>
        """
        
        # Prepare data for template
        basic_stats = self.analysis_results['basic_stats']
        
        # Determine status classes
        success_class = 'good' if basic_stats['success_rate'] >= 95 else 'bad'
        p95_class = 'good' if basic_stats['p95'] <= self.threshold_p95 else 'bad'
        
        # Build metrics table
        metrics_rows = []
        metrics = [
            ('Mean Response Time', f"{basic_stats['mean_response_time']:.0f}ms", 
             basic_stats['mean_response_time'] <= self.threshold_p95 / 2),
            ('Median Response Time', f"{basic_stats['median_response_time']:.0f}ms",
             basic_stats['median_response_time'] <= self.threshold_p95 / 2),
            ('P90 Response Time', f"{basic_stats['p90']:.0f}ms",
             basic_stats['p90'] <= self.threshold_p95),
            ('P95 Response Time', f"{basic_stats['p95']:.0f}ms",
             basic_stats['p95'] <= self.threshold_p95),
            ('P99 Response Time', f"{basic_stats['p99']:.0f}ms",
             basic_stats['p99'] <= self.threshold_p95 * 2),
            ('Error Rate', f"{100 - basic_stats['success_rate']:.2f}%",
             basic_stats['success_rate'] >= 95)
        ]
        
        for metric, value, is_good in metrics:
            status = '<span class="good">✓</span>' if is_good else '<span class="bad">✗</span>'
            metrics_rows.append(f"<tr><td>{metric}</td><td>{value}</td><td>{status}</td></tr>")
        
        # Build endpoints table
        endpoint_rows = []
        endpoint_stats = self.analysis_results['endpoint_analysis']['endpoint_stats']
        
        for endpoint, stats in sorted(endpoint_stats.items(), 
                                     key=lambda x: x[1].get('p95_response_time', 0), 
                                     reverse=True)[:10]:
            p95 = stats.get('p95_response_time', 0)
            p95_str = f"{p95:.0f}ms" if p95 > 0 else "N/A"
            
            is_good = stats['success_rate'] >= 95 and (p95 <= self.threshold_p95 if p95 > 0 else True)
            status = '<span class="good">✓</span>' if is_good else '<span class="bad">✗</span>'
            
            endpoint_rows.append(
                f"<tr><td>{endpoint}</td><td>{stats['count']}</td>"
                f"<td>{stats['success_rate']:.1f}%</td><td>{p95_str}</td>"
                f"<td>{status}</td></tr>"
            )
        
        # Generate recommendations
        recommendations = self._generate_recommendations()
        recommendations_html = '\n'.join(
            f'<div class="recommendation">{rec}</div>' for rec in recommendations
        )
        
        # Fill template
        html_content = html_template.format(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            total_requests=basic_stats['total_requests'],
            success_rate=basic_stats['success_rate'],
            success_class=success_class,
            p95=basic_stats['p95'],
            p95_class=p95_class,
            avg_rps=self.analysis_results['throughput_analysis']['avg_rps'],
            metrics_table='\n'.join(metrics_rows),
            endpoints_table='\n'.join(endpoint_rows),
            recommendations=recommendations_html
        )
        
        # Save report
        with open(output_file, 'w') as f:
            f.write(html_content)
        
        print(f"\nPerformance report saved to: {output_file}")
    
    def _generate_recommendations(self) -> List[str]:
        """Generate performance recommendations"""
        recommendations = []
        
        basic_stats = self.analysis_results['basic_stats']
        
        # Response time recommendations
        if basic_stats['p95'] > self.threshold_p95:
            recommendations.append(
                f"P95 response time ({basic_stats['p95']:.0f}ms) exceeds threshold "
                f"({self.threshold_p95}ms). Consider optimizing slow endpoints or "
                "increasing server resources."
            )
        
        # Error rate recommendations
        if basic_stats['success_rate'] < 95:
            error_analysis = self.analysis_results['error_analysis']
            recommendations.append(
                f"Success rate ({basic_stats['success_rate']:.1f}%) is below 95%. "
                f"Most common error: {error_analysis['most_common_error']}. "
                "Investigate error patterns and improve error handling."
            )
        
        # Scalability recommendations
        scalability = self.analysis_results['scalability_analysis']
        if scalability['breaking_point']:
            recommendations.append(
                f"System shows signs of stress at {scalability['breaking_point']} "
                "concurrent users. Consider horizontal scaling or performance optimization."
            )
        
        # Endpoint-specific recommendations
        problematic = self.analysis_results['endpoint_analysis']['problematic_endpoints']
        if problematic:
            recommendations.append(
                f"The following endpoints need optimization: {', '.join(problematic[:3])}. "
                "Focus on database query optimization and caching."
            )
        
        # Trend recommendations
        if self.analysis_results['response_time_analysis']['performance_trend'] == 'degrading':
            recommendations.append(
                "Performance shows degrading trend over time. This could indicate "
                "memory leaks or resource exhaustion. Monitor system resources."
            )
        
        # Throughput recommendations
        throughput = self.analysis_results['throughput_analysis']
        if throughput['avg_rps'] < 100:
            recommendations.append(
                f"Average throughput ({throughput['avg_rps']:.1f} RPS) is below "
                "expected levels. Review connection pooling and concurrency settings."
            )
        
        if not recommendations:
            recommendations.append(
                "Performance meets all defined thresholds. Continue monitoring "
                "for changes in usage patterns."
            )
        
        return recommendations


def main():
    """Main function to run performance analysis"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Analyze performance test results')
    parser.add_argument('--input', required=True, help='Input JSON file with test results')
    parser.add_argument('--threshold-p95', type=float, default=500, 
                       help='P95 response time threshold in ms')
    parser.add_argument('--output', default='performance_report.html',
                       help='Output HTML report file')
    
    args = parser.parse_args()
    
    # Run analysis
    analyzer = PerformanceAnalyzer(args.input, args.threshold_p95)
    analyzer.load_results()
    analyzer.analyze()
    analyzer.generate_report(args.output)
    
    # Check if performance meets criteria
    stats = analyzer.analysis_results['basic_stats']
    if stats['p95'] > args.threshold_p95 or stats['success_rate'] < 95:
        print("\n❌ Performance criteria NOT met!")
        exit(1)
    else:
        print("\n✅ Performance criteria met!")
        exit(0)


if __name__ == "__main__":
    main()