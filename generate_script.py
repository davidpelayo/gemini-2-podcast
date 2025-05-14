import os
import re
import asyncio
from dotenv import load_dotenv
import argparse
import json
import logging
import datetime
from pathlib import Path

load_dotenv()

# === Configure logging ===
# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Define log filename with timestamp
log_filename = logs_dir / f"generate_script_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging to both console and file
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add file handler
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

logger.info(f"Logging to file: {log_filename}")

# === Set environment variables to suppress warnings ===
os.environ['GRPC_VERBOSITY'] = 'NONE'         # Suppress gRPC logs
os.environ['GLOG_minloglevel'] = '3'         # Suppress glog logs (3 = FATAL)
logger.info("Environment variables GRPC_VERBOSITY and GLOG_minloglevel set to suppress gRPC and glog warnings.")

# === Initialize absl logging to suppress warnings ===
try:
    import absl.logging
    absl.logging.set_verbosity('error')
    absl.logging.use_absl_handler()
    logger.info("absl.logging initialized to suppress warnings.")
except ImportError:
    logger.warning("absl.logging not found, skipping its configuration.")


# === Import other modules after setting environment variables ===
from google import genai
import PyPDF2
import requests
from bs4 import BeautifulSoup

# Create both sync and async clients
logger.info("Initializing Google GenAI clients.")
client = genai.Client()
async_client = client.aio
logger.info("Google GenAI clients initialized.")

# === Rest of your code ===
def read_pdf(pdf_path):
    logger.info(f"Attempting to read PDF file: {pdf_path}")
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            logger.debug(f"Number of pages in PDF: {len(reader.pages)}")
            for i, page in enumerate(reader.pages):
                extracted = page.extract_text()
                if extracted:
                    text += extracted
                logger.debug(f"Extracted text from page {i+1}")
        logger.info(f"Successfully read PDF file: {pdf_path}")
        return text
    except FileNotFoundError:
        logger.error(f"Error: PDF file not found at path: {pdf_path}")
        return ""
    except Exception as e:
        logger.error(f"Error reading PDF file {pdf_path}: {str(e)}")
        return ""

def read_md(md_path):
    logger.info(f"Attempting to read Markdown file: {md_path}")
    try:
        with open(md_path, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.info(f"Successfully read Markdown file: {md_path}")
        return content
    except FileNotFoundError:
        logger.error(f"Error: Markdown file not found at path: {md_path}")
        return ""
    except Exception as e:
        logger.error(f"Error reading Markdown file {md_path}: {str(e)}")
        return ""

def read_url(url):
    logger.info(f"Attempting to read content from URL: {url}")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logger.debug(f"Successfully fetched URL {url} with status code {response.status_code}")
        soup = BeautifulSoup(response.text, 'html.parser')
        text_content = soup.get_text()
        logger.info(f"Successfully extracted text content from URL: {url}")
        return text_content
    except requests.exceptions.RequestException as e:
        logger.error(f"Error accessing URL {url}: {str(e)}")
        return ""
    except Exception as e:
        logger.error(f"Error processing URL content from {url}: {str(e)}")
        return ""

def read_txt(txt_path):
    logger.info(f"Attempting to read text file: {txt_path}")
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.info(f"Successfully read text file: {txt_path}")
        return content
    except FileNotFoundError:
        logger.error(f"Error: Text file not found at path: {txt_path}")
        return ""
    except Exception as e:
        logger.error(f"Error reading text file {txt_path}: {str(e)}")
        return ""

def get_content_from_source(source_type, source_path):
    logger.info(f"Getting content from source. Type: {source_type}, Path: {source_path}")
    content = ""
    
    if source_type == "pdf":
        content = read_pdf(source_path)
    elif source_type == "url":
        content = read_url(source_path)
    elif source_type == "md":
        content = read_md(source_path)
    elif source_type == "txt":
        content = read_txt(source_path)
    else:
        logger.error(f"Invalid source type: {source_type}. Must be one of: pdf, url, md, txt")
    
    if content:
        logger.info(f"Successfully retrieved content from {source_type} source.")
        logger.debug(f"Content preview (first 100 chars): {content[:100]}")
    else:
        logger.warning(f"Failed to retrieve content from {source_type} source: {source_path}")
    return content

def load_prompt_template():
    template_path = 'system_instructions_script_template.txt'
    logger.info(f"Loading prompt template from: {template_path}")
    try:
        with open(template_path, 'r', encoding='utf-8') as file:
            template_content = file.read()
        logger.info("Successfully loaded prompt template.")
        return template_content
    except FileNotFoundError:
        logger.error(f"Prompt template file not found at: {template_path}")
        raise FileNotFoundError(f"Prompt template file not found in {template_path}")

async def create_podcast_script(content, language, status_file=None):
    logger.info(f"Starting podcast script creation. Language: {language}, Status file: {status_file}")
    try:
        if status_file:
            logger.debug(f"Updating status file: {status_file} - preparing")
            update_status(status_file, "preparing", "Preparing content for script generation", 5)
        
        prompt_template = load_prompt_template()
        prompt = f"{prompt_template}\n\nOutput language: {language}\n\nContent: {content}"
        logger.debug(f"Generated prompt for Gemini. Length: {len(prompt)}")
        
        if status_file:
            logger.debug(f"Updating status file: {status_file} - generating")
            update_status(status_file, "generating", "Generating podcast script with Gemini", 10)
        
        logger.info("Calling Gemini API to generate content...")
        response = await async_client.models.generate_content(
            model='gemini-2.5-flash-preview-04-17',
            contents=prompt
        )
        logger.info("Received response from Gemini API.")
        logger.debug(f"Gemini response text (first 100 chars): {response.text[:100] if response.text else 'None'}")
        
        if status_file:
            logger.debug(f"Updating status file: {status_file} - generated")
            update_status(status_file, "generated", "Podcast script generated successfully", 90)
        
        return response.text
    except Exception as e:
        logger.error(f"Error generating content with Gemini: {str(e)}", exc_info=True)
        if status_file:
            logger.debug(f"Updating status file: {status_file} - failed due to Gemini error")
            update_status(status_file, "failed", f"Error generating script: {str(e)}", 0)
        return None
    
def clean_podcast_script(script):
    logger.info("Cleaning podcast script.")
    if not script:
        logger.warning("Script is empty or None, returning as is.")
        return script

    podcast_start_pattern = r"^(Speaker A:|Speaker B:|Speaker C:)"
    lines = script.splitlines()
    logger.debug(f"Script has {len(lines)} lines before cleaning.")
    
    for i, line in enumerate(lines):
        if re.match(podcast_start_pattern, line, re.IGNORECASE): # Added IGNORECASE for robustness
            cleaned_script = '\n'.join(lines[i:])
            logger.info(f"Podcast content found starting at line {i+1}. Cleaned script obtained.")
            logger.debug(f"Cleaned script preview (first 100 chars): {cleaned_script[:100]}")
            return cleaned_script
    
    logger.warning("No podcast start pattern (Speaker A/B/C) found. Returning original script.")
    return script

def update_status(status_file, status, message, progress):
    """Update the status file with the current progress"""
    logger.info(f"Updating status file '{status_file}': status='{status}', message='{message}', progress={progress}%")
    status_data = {
        "status": status,
        "message": message,
        "progress": progress,
        "timestamp": str(asyncio.get_event_loop().time())
    }
    
    try:
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(status_data, f, indent=2)
        logger.debug(f"Successfully wrote status to {status_file}")
    except Exception as e:
        logger.error(f"Failed to write status to {status_file}: {e}")
    
    # Also print to console for logging (this is redundant if basicConfig is used, but kept for explicitness)
    # logger.info(f"Console Status update: {status} - {message} ({progress}%)") # Redundant with logger.info above

def parse_script_args():
    logger.info("Parsing command line arguments for script generation.")
    parser = argparse.ArgumentParser(description="Generate script for podcast.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    parser.add_argument('--source-type', required=True, choices=['pdf', 'url', 'txt', 'md'], 
                        help='Type of content source (pdf, url, txt, md)')
    parser.add_argument('--source-path', required=True, help='Path or URL to the source content')
    parser.add_argument('--output-script', default='podcast_script.txt', 
                        help='Output path for the generated script file')
    parser.add_argument('--status-file', help='Path to a JSON file for tracking script generation status')
    args = parser.parse_args()
    logger.info(f"Arguments parsed: {args}")
    return args

async def main():
    logger.info("Starting main execution of generate_script.py")
    args = parse_script_args()
    
    if args.status_file:
        logger.info(f"Status file provided: {args.status_file}. Initializing status.")
        update_status(args.status_file, "started", "Starting script generation process", 0)
    
    logger.info(f"Extracting content from {args.source_type} source: {args.source_path}")
    if args.status_file:
        update_status(args.status_file, "extracting", f"Extracting content from {args.source_type} source", 2)
    
    content = get_content_from_source(args.source_type, args.source_path)
    if not content:
        error_msg = f"Error: Could not extract content from {args.source_type} source at {args.source_path}"
        logger.error(error_msg)
        if args.status_file:
            update_status(args.status_file, "failed", error_msg, 0)
        logger.info("Exiting due to content extraction failure.")
        return
    
    logger.info("Content extracted successfully. Proceeding to generate podcast script.")
    script = await create_podcast_script(content, args.language, args.status_file)
    
    if script:
        logger.info("Podcast script generated. Proceeding to clean and save.")
        if args.status_file:
            update_status(args.status_file, "processing", "Processing and cleaning the generated script", 95)
        
        cleaned_script = clean_podcast_script(script)
        
        logger.info(f"Saving cleaned script to: {args.output_script}")
        try:
            with open(args.output_script, "w", encoding='utf-8') as f:
                f.write(cleaned_script)
            logger.info(f"Successfully saved cleaned script to {args.output_script}")
        except Exception as e:
            error_msg = f"Failed to save script to {args.output_script}: {e}"
            logger.error(error_msg)
            if args.status_file:
                update_status(args.status_file, "failed", error_msg, 98) # Progress before 100
            logger.info("Exiting due to script saving failure.")
            return

        success_msg = f"Podcast script saved successfully to {args.output_script}!"
        logger.info(success_msg)
        
        if args.status_file:
            update_status(args.status_file, "completed", success_msg, 100)
    else:
        logger.error("Failed to generate podcast script (script is None).")
        # Check if status file exists and if it already indicates failure
        already_failed = False
        if args.status_file and os.path.exists(args.status_file):
            try:
                with open(args.status_file, 'r') as sf:
                    status_data = json.load(sf)
                    if status_data.get("status") == "failed":
                        already_failed = True
                        logger.info("Status file already indicates failure. No further update needed.")
            except Exception as e:
                logger.warning(f"Could not read status file {args.status_file} to check for existing failure: {e}")

        if args.status_file and not already_failed:
            update_status(args.status_file, "failed", "Failed to generate podcast script", 0)
    logger.info("Main execution of generate_script.py finished.")

if __name__ == "__main__":
    logger.info("generate_script.py executed as main script.")
    asyncio.run(main())
