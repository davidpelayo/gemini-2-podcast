import subprocess
import os
import logging
import sys
import argparse

# Custom formatter that only shows the message
class CustomFormatter(logging.Formatter):
    def format(self, record):
        return record.getMessage()

# Configure logging with custom formatter
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(CustomFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)
# Remove default handlers
logging.getLogger().handlers = []

def parse_arguments():
    parser = argparse.ArgumentParser(description="Generate podcast from source content.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    parser.add_argument('--source-type', required=True, choices=['pdf', 'url', 'txt', 'md'], 
                      help='Type of content source (pdf, url, txt, md)')
    parser.add_argument('--source-path', required=True, help='Path or URL to the source content')
    parser.add_argument('--output-script', default='podcast_script.txt', 
                      help='Output path for the generated script file')
    parser.add_argument('--output-podcast', default='final_podcast.wav', 
                      help='Output path for the generated podcast audio file')
    return parser.parse_args()

def update_language_in_template(language):
    template_file = 'system_instructions_audio_template.txt'
    output_file = 'system_instructions_audio.txt'
    
    with open(template_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    updated_content = content.replace('[LANGUAGE]', language)
    
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(updated_content)

def generate_podcast(args):
    try:
        # Update language in template file
        update_language_in_template(args.language)
        logger.info(f"Updated template for language: {args.language}")

        # Step 1: Generate script
        logger.info("Generating podcast script...")
        script_cmd = [
            sys.executable, 
            "generate_script.py", 
            "--language", args.language,
            "--source-type", args.source_type,
            "--source-path", args.source_path,
            "--output-script", args.output_script
        ]
        subprocess.run(script_cmd, check=True)
        logger.info(f"Script generated at {args.output_script}")
        
        # Step 2: Generate audio
        logger.info("Converting script to audio...")
        audio_cmd = [
            sys.executable, 
            "generate_audio.py", 
            "--language", args.language,
            "--input-script", args.output_script,
            "--output-podcast", args.output_podcast
        ]
        subprocess.run(audio_cmd, check=True)
        
        if os.path.exists(args.output_podcast):
            logger.info(f"Podcast generation complete! Output: {args.output_podcast}")
        else:
            logger.error("Failed to generate final podcast audio")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Process failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    args = parse_arguments()
    generate_podcast(args)
