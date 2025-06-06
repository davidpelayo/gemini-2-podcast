import json
import boto3
import os
import logging
import uuid
from typing import Dict, Any, Optional
import google.generativeai as genai

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
s3_client = boto3.client('s3')
ssm_client = boto3.client('ssm')

def get_parameter(parameter_name: str) -> str:
    """Get parameter from AWS Systems Manager Parameter Store."""
    try:
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        return response['Parameter']['Value']
    except Exception as e:
        logger.error(f"Error getting parameter {parameter_name}: {str(e)}")
        raise

def get_s3_object(bucket: str, key: str) -> str:
    """Get object content from S3."""
    try:
        response = s3_client.get_object(Bucket=bucket, Key=key)
        return response['Body'].read().decode('utf-8')
    except Exception as e:
        logger.error(f"Error getting S3 object s3://{bucket}/{key}: {str(e)}")
        raise

def save_to_s3(bucket_name: str, key: str, content: str, metadata: Dict[str, str] = None) -> bool:
    """Save content to S3 bucket."""
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=content,
            ContentType='text/plain',
            Metadata=metadata or {}
        )
        logger.info(f"Successfully saved to S3: s3://{bucket_name}/{key}")
        return True
    except Exception as e:
        logger.error(f"Error saving to S3: {str(e)}")
        return False

def update_status(status_bucket: str, podcast_id: str, status: str, message: str, progress: int):
    """Update podcast generation status in S3."""
    try:
        status_data = {
            "status": status,
            "message": message,
            "progress": progress,
            "timestamp": str(uuid.uuid4())  # Simple timestamp replacement
        }
        
        status_key = f"status/{podcast_id}.json"
        s3_client.put_object(
            Bucket=status_bucket,
            Key=status_key,
            Body=json.dumps(status_data),
            ContentType='application/json'
        )
        logger.info(f"Status updated: {status} - {message} ({progress}%)")
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}")

def generate_script_with_gemini(transcript: str, language: str = "English") -> str:
    """Generate podcast script using Gemini AI."""
    try:
        # Get Google API key
        api_key = get_parameter(f"/podrun/{os.environ.get('ENVIRONMENT', 'dev')}/google-api-key")
        genai.configure(api_key=api_key)
        
        # Initialize the model
        model = genai.GenerativeModel('gemini-pro')
        
        # Create the prompt for script generation
        prompt = f"""
        Transform the following transcript into an engaging podcast script in {language}. 
        Create a natural conversation between two hosts discussing the content.
        
        Guidelines:
        - Make it conversational and engaging
        - Add natural transitions and commentary
        - Include questions and responses between hosts
        - Maintain the key information from the original content
        - Format as a script with HOST1 and HOST2 labels
        
        Original transcript:
        {transcript}
        
        Generate the podcast script:
        """
        
        # Generate the script
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        logger.error(f"Error generating script with Gemini: {str(e)}")
        raise

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for podcast script generation.
    
    Expected event structure:
    {
        "transcriptPath": "s3://bucket/path/to/transcript.txt",
        "podcastId": "unique-podcast-id",
        "language": "English",
        "videoTitle": "Video Title"
    }
    """
    try:
        # Parse the event
        if 'body' in event:
            # API Gateway event
            body = json.loads(event['body']) if isinstance(event['body'], str) else event['body']
        else:
            # Direct Lambda invocation
            body = event
        
        transcript_path = body.get('transcriptPath')
        podcast_id = body.get('podcastId', str(uuid.uuid4()))
        language = body.get('language', 'English')
        video_title = body.get('videoTitle', 'Podcast')
        
        if not transcript_path:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Transcript path is required'
                })
            }
        
        # Get bucket names from Parameter Store
        environment = os.environ.get('ENVIRONMENT', 'dev')
        scripts_bucket = get_parameter(f"/podrun/{environment}/s3/scripts-bucket")
        status_bucket = get_parameter(f"/podrun/{environment}/s3/status-bucket")
        
        # Update status - starting script generation
        update_status(status_bucket, podcast_id, "processing", "Starting script generation", 10)
        
        # Parse S3 path
        if transcript_path.startswith('s3://'):
            path_parts = transcript_path[5:].split('/', 1)
            transcript_bucket = path_parts[0]
            transcript_key = path_parts[1]
        else:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Invalid transcript path format. Must be s3://bucket/key'
                })
            }
        
        # Get transcript from S3
        logger.info(f"Fetching transcript from s3://{transcript_bucket}/{transcript_key}")
        update_status(status_bucket, podcast_id, "processing", "Fetching transcript", 20)
        
        transcript_content = get_s3_object(transcript_bucket, transcript_key)
        
        # Generate script using Gemini
        logger.info("Generating script with Gemini AI")
        update_status(status_bucket, podcast_id, "processing", "Generating script with AI", 50)
        
        script_content = generate_script_with_gemini(transcript_content, language)
        
        # Save script to S3
        script_key = f"scripts/{podcast_id}/script.txt"
        script_metadata = {
            'podcast-id': podcast_id,
            'language': language,
            'video-title': video_title,
            'source-transcript': transcript_path
        }
        
        logger.info(f"Saving script to s3://{scripts_bucket}/{script_key}")
        update_status(status_bucket, podcast_id, "processing", "Saving script", 80)
        
        success = save_to_s3(scripts_bucket, script_key, script_content, script_metadata)
        
        if not success:
            update_status(status_bucket, podcast_id, "failed", "Failed to save script", 80)
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Failed to save script to S3'
                })
            }
        
        # Update status - script generation completed
        update_status(status_bucket, podcast_id, "completed", "Script generation completed", 100)
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': True,
                'podcastId': podcast_id,
                'scriptPath': f"s3://{scripts_bucket}/{script_key}",
                'message': 'Script generated successfully'
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        
        # Update status on error
        if 'podcast_id' in locals() and 'status_bucket' in locals():
            update_status(status_bucket, podcast_id, "failed", f"Script generation failed: {str(e)}", 0)
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error'
            })
        } 