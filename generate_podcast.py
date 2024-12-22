import subprocess
import os
import logging
import sys

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

def generate_podcast():
    try:
        # Step 1: Generate script
        logger.info("Generating podcast script...")
        subprocess.run([sys.executable, "generate_script.py"], check=True)
        
        # Pause for user acknowledgment
        user_input = input("Script generated at podcast_script.txt. Press Enter to proceed to audio generation or 'q' to quit: ")
        if user_input.lower() == 'q':
            logger.info("Process terminated by user.")
            return

        # Step 2: Generate audio
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
    generate_podcast()