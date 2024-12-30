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
    parser = argparse.ArgumentParser(description="Generate podcast with language option.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    return parser.parse_args()

def update_language_in_template(language):
    template_file = 'system_instructions_audio_template.txt'
    output_file = 'system_instructions_audio.txt'
    
    with open(template_file, 'r', encoding='utf-8') as file:
        content = file.read()
    
    updated_content = content.replace('[LANGUAGE]', language)
    
    with open(output_file, 'w', encoding='utf-8') as file:
        file.write(updated_content)

def generate_podcast(language):
    try:
        # Update language in template file
        update_language_in_template(language)
        logger.info(f"Updated template for language: {language}")

        # Step 1: Generate script
        logger.info("Generating podcast script...")
        subprocess.run([sys.executable, "generate_script.py"], check=True)
        
        # Pause for user acknowledgment
        user_input = input("Script generated at podcast_script.txt. Press Enter to proceed to audio generation or 'q' to quit: ")
        if user_input.lower() == 'q':
            logger.info("Process terminated by user.")
            return

        # Step 2: Generate audio with updated language file
        logger.info("Converting script to audio...")
        subprocess.run([sys.executable, "generate_audio.py"], check=True)
        
        if os.path.exists("final_podcast.wav"):
            logger.info("Podcast generation complete! Output: final_podcast.wav")
        else:
            logger.error("Failed to generate final podcast audio")
            
    except subprocess.CalledProcessError as e:
        logger.error(f"Process failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    args = parse_arguments()
    generate_podcast(args.language)
