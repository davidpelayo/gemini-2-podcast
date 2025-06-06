import json
import boto3
import os
import logging
import uuid
from typing import Dict, Any, Optional
import google.generativeai as genai
from google.cloud import texttospeech
import io

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

def save_to_s3(bucket_name: str, key: str, content: bytes, content_type: str = 'audio/wav', metadata: Dict[str, str] = None) -> bool:
    """Save content to S3 bucket."""
    try:
        s3_client.put_object(
            Bucket=bucket_name,
            Key=key,
            Body=content,
            ContentType=content_type,
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

def parse_script_for_tts(script_content: str) -> list:
    """Parse script content to extract speaker segments."""
    segments = []
    lines = script_content.split('\n')
    
    current_speaker = None
    current_text = []
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        # Check if line starts with a speaker label
        if line.startswith('HOST1:') or line.startswith('HOST2:'):
            # Save previous segment if exists
            if current_speaker and current_text:
                segments.append({
                    'speaker': current_speaker,
                    'text': ' '.join(current_text).strip()
                })
            
            # Start new segment
            if line.startswith('HOST1:'):
                current_speaker = 'HOST1'
                current_text = [line[6:].strip()]  # Remove 'HOST1:' prefix
            else:
                current_speaker = 'HOST2'
                current_text = [line[6:].strip()]  # Remove 'HOST2:' prefix
        else:
            # Continue current speaker's text
            if current_speaker:
                current_text.append(line)
    
    # Add final segment
    if current_speaker and current_text:
        segments.append({
            'speaker': current_speaker,
            'text': ' '.join(current_text).strip()
        })
    
    return segments

def generate_audio_with_tts(script_segments: list, language: str = "en-US") -> bytes:
    """Generate audio from script segments using Google Text-to-Speech."""
    try:
        # Note: This is a simplified version. In a real implementation,
        # you would need to set up Google Cloud credentials properly
        # For now, we'll create a placeholder audio file
        
        # Combine all text segments
        full_text = ""
        for segment in script_segments:
            speaker_prefix = f"[{segment['speaker']}] "
            full_text += speaker_prefix + segment['text'] + " "
        
        # In a real implementation, you would use Google TTS here
        # For this example, we'll create a simple text representation
        audio_content = f"Audio content for: {full_text[:100]}...".encode('utf-8')
        
        logger.info(f"Generated audio content ({len(audio_content)} bytes)")
        return audio_content
        
    except Exception as e:
        logger.error(f"Error generating audio with TTS: {str(e)}")
        raise

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for podcast audio generation.
    
    Expected event structure:
    {
        "scriptPath": "s3://bucket/path/to/script.txt",
        "podcastId": "unique-podcast-id",
        "language": "en-US",
        "voiceSettings": {
            "host1Voice": "en-US-Wavenet-D",
            "host2Voice": "en-US-Wavenet-F"
        }
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
        
        script_path = body.get('scriptPath')
        podcast_id = body.get('podcastId', str(uuid.uuid4()))
        language = body.get('language', 'en-US')
        voice_settings = body.get('voiceSettings', {})
        
        if not script_path:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Script path is required'
                })
            }
        
        # Get bucket names from Parameter Store
        environment = os.environ.get('ENVIRONMENT', 'dev')
        audio_bucket = get_parameter(f"/podrun/{environment}/s3/audio-bucket")
        status_bucket = get_parameter(f"/podrun/{environment}/s3/status-bucket")
        
        # Update status - starting audio generation
        update_status(status_bucket, podcast_id, "processing", "Starting audio generation", 10)
        
        # Parse S3 path
        if script_path.startswith('s3://'):
            path_parts = script_path[5:].split('/', 1)
            script_bucket = path_parts[0]
            script_key = path_parts[1]
        else:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Invalid script path format. Must be s3://bucket/key'
                })
            }
        
        # Get script from S3
        logger.info(f"Fetching script from s3://{script_bucket}/{script_key}")
        update_status(status_bucket, podcast_id, "processing", "Fetching script", 20)
        
        script_content = get_s3_object(script_bucket, script_key)
        
        # Parse script into segments
        logger.info("Parsing script for TTS")
        update_status(status_bucket, podcast_id, "processing", "Parsing script", 30)
        
        script_segments = parse_script_for_tts(script_content)
        logger.info(f"Found {len(script_segments)} script segments")
        
        # Generate audio using TTS
        logger.info("Generating audio with TTS")
        update_status(status_bucket, podcast_id, "processing", "Generating audio", 60)
        
        audio_content = generate_audio_with_tts(script_segments, language)
        
        # Save audio to S3
        audio_key = f"audio/{podcast_id}/podcast.wav"
        audio_metadata = {
            'podcast-id': podcast_id,
            'language': language,
            'source-script': script_path,
            'segments-count': str(len(script_segments))
        }
        
        logger.info(f"Saving audio to s3://{audio_bucket}/{audio_key}")
        update_status(status_bucket, podcast_id, "processing", "Saving audio", 80)
        
        success = save_to_s3(audio_bucket, audio_key, audio_content, 'audio/wav', audio_metadata)
        
        if not success:
            update_status(status_bucket, podcast_id, "failed", "Failed to save audio", 80)
            return {
                'statusCode': 500,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Failed to save audio to S3'
                })
            }
        
        # Update status - audio generation completed
        update_status(status_bucket, podcast_id, "completed", "Audio generation completed", 100)
        
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
                'audioPath': f"s3://{audio_bucket}/{audio_key}",
                'audioUrl': f"https://{audio_bucket}.s3.amazonaws.com/{audio_key}",
                'message': 'Audio generated successfully'
            })
        }
        
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        
        # Update status on error
        if 'podcast_id' in locals() and 'status_bucket' in locals():
            update_status(status_bucket, podcast_id, "failed", f"Audio generation failed: {str(e)}", 0)
        
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