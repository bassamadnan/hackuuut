import boto3
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

def list_s3_buckets() -> List[Dict[str, Any]]:
    """
    List all S3 buckets in the AWS account with size and last modified info.
    
    Returns:
        List of dictionaries containing bucket information
    """
    try:
        # Initialize boto3 clients
        s3_client = boto3.client('s3')
        cloudwatch = boto3.client('cloudwatch')
        
        # Get list of buckets
        response = s3_client.list_buckets()
        
        bucket_data = []
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            creation_date = bucket['CreationDate']
            
            # Get bucket size metrics from CloudWatch
            try:
                size_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/S3',
                    MetricName='BucketSizeBytes',
                    Dimensions=[
                        {'Name': 'BucketName', 'Value': bucket_name},
                        {'Name': 'StorageType', 'Value': 'StandardStorage'}
                    ],
                    StartTime=datetime.now() - timedelta(days=2),
                    EndTime=datetime.now(),
                    Period=86400,  # 1 day in seconds
                    Statistics=['Average']
                )
                
                if 'Datapoints' in size_response and size_response['Datapoints']:
                    bucket_size = size_response['Datapoints'][-1]['Average'] / (1024 * 1024 * 1024)  # Convert to GB
                else:
                    bucket_size = 0
            except Exception:
                bucket_size = 0
                
            # Get bucket object count metrics
            try:
                object_count_response = cloudwatch.get_metric_statistics(
                    Namespace='AWS/S3',
                    MetricName='NumberOfObjects',
                    Dimensions=[
                        {'Name': 'BucketName', 'Value': bucket_name},
                        {'Name': 'StorageType', 'Value': 'AllStorageTypes'}
                    ],
                    StartTime=datetime.now() - timedelta(days=2),
                    EndTime=datetime.now(),
                    Period=86400,  # 1 day in seconds
                    Statistics=['Average']
                )
                
                if 'Datapoints' in object_count_response and object_count_response['Datapoints']:
                    object_count = int(object_count_response['Datapoints'][-1]['Average'])
                else:
                    object_count = 0
            except Exception:
                object_count = 0
            
            bucket_data.append({
                'name': bucket_name,
                'creation_date': creation_date.strftime('%Y-%m-%d %H:%M:%S'),
                'size_gb': round(bucket_size, 2),
                'object_count': object_count
            })
        
        return bucket_data
    except Exception as e:
        print(f"Error listing S3 buckets: {str(e)}")
        return []

def describe_ec2_instance(instance_id: str) -> Dict[str, Any]:
    """
    Get detailed information about an EC2 instance.
    
    Args:
        instance_id: The ID of the EC2 instance to describe
        
    Returns:
        Dictionary containing instance information
    """
    try:
        ec2_client = boto3.client('ec2')
        
        # Get instance details
        response = ec2_client.describe_instances(InstanceIds=[instance_id])
        
        if not response['Reservations'] or not response['Reservations'][0]['Instances']:
            return {'error': f'Instance {instance_id} not found'}
        
        instance = response['Reservations'][0]['Instances'][0]
        
        # Get CloudWatch metrics for CPU utilization
        cloudwatch = boto3.client('cloudwatch')
        cpu_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/EC2',
            MetricName='CPUUtilization',
            Dimensions=[{'Name': 'InstanceId', 'Value': instance_id}],
            StartTime=datetime.now() - timedelta(days=7),
            EndTime=datetime.now(),
            Period=86400,  # 1 day in seconds
            Statistics=['Average', 'Maximum']
        )
        
        # Process CPU utilization data
        cpu_data = []
        for point in sorted(cpu_response['Datapoints'], key=lambda x: x['Timestamp']):
            cpu_data.append({
                'date': point['Timestamp'].strftime('%Y-%m-%d'),
                'average': round(point['Average'], 2),
                'maximum': round(point['Maximum'], 2)
            })
        
        # Construct instance information
        instance_info = {
            'instance_id': instance_id,
            'instance_type': instance.get('InstanceType', 'Unknown'),
            'state': instance.get('State', {}).get('Name', 'Unknown'),
            'launch_time': instance.get('LaunchTime', datetime.now()).strftime('%Y-%m-%d %H:%M:%S'),
            'public_ip': instance.get('PublicIpAddress', 'None'),
            'private_ip': instance.get('PrivateIpAddress', 'None'),
            'availability_zone': instance.get('Placement', {}).get('AvailabilityZone', 'Unknown'),
            'vpc_id': instance.get('VpcId', 'None'),
            'subnet_id': instance.get('SubnetId', 'None'),
            'cpu_utilization': cpu_data,
            'tags': instance.get('Tags', [])
        }
        
        return instance_info
    except Exception as e:
        print(f"Error describing EC2 instance: {str(e)}")
        return {'error': str(e)}

def search_logs(log_group: str, search_term: str, hours: int = 24) -> List[Dict[str, Any]]:
    """
    Search CloudWatch logs for specific terms.
    
    Args:
        log_group: The CloudWatch log group to search
        search_term: The term to search for in the logs
        hours: Number of hours to look back (default: 24)
        
    Returns:
        List of log events matching the search term
    """
    try:
        logs_client = boto3.client('logs')
        
        # Calculate start and end time
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(hours=hours)).timestamp() * 1000)
        
        # Create filter pattern
        filter_pattern = f'"{search_term}"'
        
        # Initialize pagination token and results
        next_token = None
        all_events = []
        
        # Get log events with pagination
        while True:
            if next_token:
                response = logs_client.filter_log_events(
                    logGroupName=log_group,
                    filterPattern=filter_pattern,
                    startTime=start_time,
                    endTime=end_time,
                    nextToken=next_token
                )
            else:
                response = logs_client.filter_log_events(
                    logGroupName=log_group,
                    filterPattern=filter_pattern,
                    startTime=start_time,
                    endTime=end_time
                )
            
            # Process log events
            for event in response['events']:
                timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                all_events.append({
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'message': event['message'],
                    'log_stream': event['logStreamName']
                })
            
            # Check for pagination
            if 'nextToken' in response:
                next_token = response['nextToken']
            else:
                break
                
        return all_events
    except Exception as e:
        print(f"Error searching logs: {str(e)}")
        return []

def get_error_count(log_group: str, error_terms: List[str] = None, days: int = 7) -> Dict[str, Any]:
    """
    Get count of errors from CloudWatch logs grouped by day.
    
    Args:
        log_group: The CloudWatch log group to analyze
        error_terms: List of error terms to search for (default: ['error', 'exception', 'fail', 'timeout'])
        days: Number of days to look back (default: 7)
        
    Returns:
        Dictionary with error counts by day and term
    """
    if error_terms is None:
        error_terms = ['error', 'exception', 'fail', 'timeout']
    
    try:
        logs_client = boto3.client('logs')
        
        # Calculate start and end time
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        results = {
            'total_errors': 0,
            'errors_by_day': {},
            'errors_by_term': {term: 0 for term in error_terms}
        }
        
        # Search for each error term
        for error_term in error_terms:
            filter_pattern = f'"{error_term}"'
            next_token = None
            
            # Get log events with pagination
            while True:
                if next_token:
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        filterPattern=filter_pattern,
                        startTime=start_time,
                        endTime=end_time,
                        nextToken=next_token
                    )
                else:
                    response = logs_client.filter_log_events(
                        logGroupName=log_group,
                        filterPattern=filter_pattern,
                        startTime=start_time,
                        endTime=end_time
                    )
                
                # Process log events
                for event in response['events']:
                    timestamp = datetime.fromtimestamp(event['timestamp'] / 1000)
                    day = timestamp.strftime('%Y-%m-%d')
                    
                    # Update counts
                    if day not in results['errors_by_day']:
                        results['errors_by_day'][day] = 0
                    
                    results['errors_by_day'][day] += 1
                    results['errors_by_term'][error_term] += 1
                    results['total_errors'] += 1
                
                # Check for pagination
                if 'nextToken' in response:
                    next_token = response['nextToken']
                else:
                    break
        
        # Sort days for better presentation
        sorted_days = sorted(results['errors_by_day'].keys())
        results['errors_by_day'] = {day: results['errors_by_day'][day] for day in sorted_days}
        
        return results
    except Exception as e:
        print(f"Error getting error count: {str(e)}")
        return {
            'error': str(e),
            'total_errors': 0,
            'errors_by_day': {},
            'errors_by_term': {term: 0 for term in error_terms}
        }