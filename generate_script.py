import os
import re
from dotenv import load_dotenv
import argparse

load_dotenv()

# === Set environment variables to suppress warnings ===
os.environ['GRPC_VERBOSITY'] = 'NONE'         # Suppress gRPC logs
os.environ['GLOG_minloglevel'] = '3'         # Suppress glog logs (3 = FATAL)

# === Initialize absl logging to suppress warnings ===
import absl.logging
absl.logging.set_verbosity('error')
absl.logging.use_absl_handler()

# === Import other modules after setting environment variables ===
import google.generativeai as genai
import PyPDF2
import requests
from bs4 import BeautifulSoup

# === Rest of your code ===
def read_pdf(pdf_path):
    try:
        with open(pdf_path, 'rb') as file:
            reader = PyPDF2.PdfReader(file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
        return text
    except FileNotFoundError:
        print(f"Error: PDF file not found at path: {pdf_path}")
        return ""
    except Exception as e:
        print(f"Error reading PDF file: {str(e)}")
        return ""

def read_md(md_path):
    try:
        with open(md_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: Markdown file not found at path: {md_path}")
        return ""
    except Exception as e:
        print(f"Error reading Markdown file: {str(e)}")
        return ""

def read_url(url):
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        return soup.get_text()
    except requests.exceptions.RequestException as e:
        print(f"Error accessing URL: {str(e)}")
        return ""
    except Exception as e:
        print(f"Error processing URL content: {str(e)}")
        return ""

def read_txt(txt_path):
    try:
        with open(txt_path, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"Error: Text file not found at path: {txt_path}")
        return ""
    except Exception as e:
        print(f"Error reading text file: {str(e)}")
        return ""

def get_content_from_source(source_type, source_path):
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
        print(f"Invalid source type: {source_type}. Must be one of: pdf, url, md, txt")
        
    return content

def load_prompt_template():
    try:
        with open('system_instructions_script_template.txt', 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        raise FileNotFoundError("Prompt template file not found in system_instructions_script_template.txt")

def create_podcast_script(content, language):
    try:
        # Initialize Gemini
        genai.configure(api_key=os.getenv('GOOGLE_API_KEY'))
        model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')

        # Load prompt template and format with content
        prompt_template = load_prompt_template()
        prompt = f"{prompt_template}\n\nOutput language: {language}\n\nContent: {content}"
        
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        print(f"Error generating content: {str(e)}")
        return None
    
def clean_podcast_script(script):
    # Define a regex pattern to identify the start of the podcast text
    podcast_start_pattern = r"^(Speaker A:|Speaker B:|Speaker C:)"
    
    # Split the script into lines
    lines = script.splitlines()
    
    # Find the first line that matches the podcast start pattern
    for i, line in enumerate(lines):
        if re.match(podcast_start_pattern, line):
            # Return the script starting from the first podcast line
            return '\n'.join(lines[i:])
    
    # If no match is found, return the original script
    return script

def parse_script_args():
    parser = argparse.ArgumentParser(description="Generate script for podcast.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    parser.add_argument('--source-type', required=True, choices=['pdf', 'url', 'txt', 'md'], 
                        help='Type of content source (pdf, url, txt, md)')
    parser.add_argument('--source-path', required=True, help='Path or URL to the source content')
    parser.add_argument('--output-script', default='podcast_script.txt', 
                        help='Output path for the generated script file')
    return parser.parse_args()

def main():
    args = parse_script_args()
    
    # Get content from specified source
    content = get_content_from_source(args.source_type, args.source_path)
    if not content:
        print(f"Error: Could not extract content from {args.source_type} source at {args.source_path}")
        return
        
    # Generate podcast script
    script = create_podcast_script(content, args.language)
    if script:
        # Clean the script before saving
        cleaned_script = clean_podcast_script(script)
        
        # Save the cleaned script to the specified output path
        with open(args.output_script, "w", encoding='utf-8') as f:
            f.write(cleaned_script)
        print(f"Podcast script saved successfully to {args.output_script}!")

if __name__ == "__main__":
    main()
