import subprocess
import os
import logging
import sys
import argparse
import json
import time
import datetime
from pathlib import Path

# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Define log filename with timestamp
log_filename = logs_dir / f"generate_podcast_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

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

# Add file handler with detailed formatting
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(file_handler)

# Check if we are in a test environment or if default handlers are already removed
if not any(isinstance(h, logging.StreamHandler) and h.formatter == handler for h in logging.getLogger().handlers):
    logging.getLogger().handlers = [] # Clear existing handlers only if not already set up by this script
    logger.addHandler(handler) # Re-add our specific handler if cleared

logger.info(f"Logging to file: {log_filename}")
logger.info("Logger configured for generate_podcast.py")

def parse_arguments():
    logger.info("Parsing command-line arguments...")
    parser = argparse.ArgumentParser(description="Generate podcast from source content.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    parser.add_argument('--source-type', required=True, choices=['pdf', 'url', 'txt', 'md'], 
                      help='Type of content source (pdf, url, txt, md)')
    parser.add_argument('--source-path', required=True, help='Path or URL to the source content')
    parser.add_argument('--output-script', default='podcast_script.txt', 
                      help='Output path for the generated script file')
    parser.add_argument('--output-podcast', default='final_podcast.wav', 
                      help='Output path for the generated podcast audio file')
    parser.add_argument('--status-file', help='Path to status file for tracking progress')
    args = parser.parse_args()
    logger.info(f"Arguments parsed: {args}")
    return args

def update_language_in_template(language):
    logger.info(f"Updating language in template to: {language}")
    template_file = 'system_instructions_audio_template.txt'
    output_file = 'system_instructions_audio.txt'
    logger.info(f"Template file: {template_file}, Output file: {output_file}")
    
    try:
        logger.info(f"Reading template file: {template_file}")
        with open(template_file, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.info("Template file read successfully.")
        
        updated_content = content.replace('[LANGUAGE]', language)
        logger.info(f"Content updated with language: {language}")
        
        logger.info(f"Writing updated content to: {output_file}")
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(updated_content)
        logger.info("Updated content written successfully.")
    except Exception as e:
        logger.error(f"Error updating language in template: {e}")
        raise
    logger.info("Finished updating language in template.")

def update_status(status_file, status, message, progress, phase="script"):
    logger.info(f"Attempting to update status: file='{status_file}', status='{status}', message='{message}', progress={progress}%, phase='{phase}'")
    if not status_file:
        logger.info("No status file provided. Skipping status update.")
        return
        
    overall_status = {}
    logger.info(f"Checking if status file exists: {status_file}")
    if os.path.exists(status_file):
        try:
            logger.info(f"Status file exists. Reading content from {status_file}.")
            with open(status_file, 'r', encoding='utf-8') as f:
                overall_status = json.load(f)
            logger.info(f"Successfully loaded existing status: {overall_status}")
        except Exception as e:
            logger.warning(f"Could not read or parse status file {status_file}: {e}. Initializing with empty status.")
            overall_status = {}
    else:
        logger.info(f"Status file {status_file} does not exist. Initializing with empty status.")
    
    logger.info(f"Updating phase-specific status for '{phase}'.")
    overall_status[phase] = {
        "status": status,
        "message": message,
        "progress": progress,
        "timestamp": time.time()
    }
    logger.info(f"Phase '{phase}' status updated to: {overall_status[phase]}")
    
    script_progress = overall_status.get("script", {}).get("progress", 0)
    audio_progress = overall_status.get("audio", {}).get("progress", 0)
    logger.info(f"Current script progress: {script_progress}%, Current audio progress: {audio_progress}%")
    
    if status == "failed" and (phase == "script" or phase == "audio"): # If any main phase fails, overall fails
        logger.info(f"Phase '{phase}' reported failure. Setting overall status to failed.")
        overall_progress = overall_status.get(phase, {}).get("progress", 0) # Keep phase progress
        overall_status["status"] = "failed"
        # Use the most recent failure message for the overall message
        overall_status["message"] = f"Error in {phase} phase: {message}"
        # Keep individual phase progress, but overall progress reflects the point of failure.
        # For simplicity, if a phase fails, its contribution to overall progress might be considered 0 for the failed part.
        # Let's adjust overall progress calculation to reflect this.
        # If script fails, overall progress is script_progress * 0.4.
        # If audio fails, overall progress is (100 * 0.4) + (audio_progress * 0.6)
        if phase == "script":
             overall_progress = (progress * 0.4) # progress of script phase at point of failure
        elif phase == "audio":
             overall_progress = (overall_status.get("script", {}).get("progress", 100) * 0.4) + (progress * 0.6) # progress of audio phase at point of failure

    else:
        overall_progress = (script_progress * 0.4) + (audio_progress * 0.6)
        logger.info(f"Calculated overall progress: {overall_progress}%")
        
        if phase == "audio" and status == "completed" and script_progress == 100:
            logger.info("Audio phase completed and script phase was completed. Setting overall status to completed.")
            overall_status["status"] = "completed"
            overall_status["message"] = "Podcast generation complete"
            overall_progress = 100 # Ensure it's exactly 100
        elif overall_status.get("status") != "failed": # Don't override if already failed
            logger.info("Setting overall status to processing.")
            overall_status["status"] = "processing"
            overall_status["message"] = f"{phase.capitalize()} phase: {message}" # More specific overall message

    overall_status["progress"] = min(max(overall_progress, 0), 100) # Clamp progress between 0 and 100
    logger.info(f"Final overall status: {overall_status['status']}, Overall message: {overall_status['message']}, Overall progress: {overall_status['progress']}%")
    
    try:
        logger.info(f"Saving updated status to {status_file}.")
        with open(status_file, 'w', encoding='utf-8') as f:
            json.dump(overall_status, f, indent=2)
        logger.info("Status saved successfully.")
    except Exception as e:
        logger.error(f"Failed to write status to {status_file}: {e}")
    
    logger.info(f"Status update [{phase}]: {status} - {message} ({progress}%)") # This is the console log from original
    logger.info(f"Finished update_status for phase '{phase}'.")

def generate_podcast(args):
    logger.info(f"Starting podcast generation with arguments: {args}")
    try:
        if args.status_file:
            logger.info(f"Initializing status file: {args.status_file}")
            update_status(args.status_file, "started", "Starting podcast generation process", 0, "overall_process") # Using a distinct phase
        
        logger.info("Updating language in template...")
        update_language_in_template(args.language)
        logger.info(f"Successfully updated template for language: {args.language}")

        script_status_file = f"{args.status_file}.script" if args.status_file else None
        logger.info(f"Script status file will be: {script_status_file}")
        
        # Step 1: Generate script
        logger.info("=== Starting Step 1: Generate script ===")
        if args.status_file:
            logger.info("Updating status for script generation start.")
            update_status(args.status_file, "processing", "Initializing script generation", 1, "script") # Small progress for init
        
        script_cmd = [
            sys.executable, 
            "generate_script.py", 
            "--language", args.language,
            "--source-type", args.source_type,
            "--source-path", args.source_path,
            "--output-script", args.output_script
        ]
        
        if script_status_file:
            logger.info(f"Adding script status file to command: {script_status_file}")
            script_cmd.extend(["--status-file", script_status_file])
        
        logger.info(f"Script generation command: {' '.join(script_cmd)}")
        logger.info("Starting script generation subprocess...")
        script_process = subprocess.Popen(
            script_cmd, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8'
        )
        logger.info(f"Script generation subprocess started (PID: {script_process.pid}).")
        
        logger.info("Monitoring script generation status...")
        while script_process.poll() is None:
            logger.info("Script process is still running...")
            if args.status_file and script_status_file and os.path.exists(script_status_file):
                logger.info(f"Script status file {script_status_file} exists. Attempting to read.")
                try:
                    with open(script_status_file, 'r', encoding='utf-8') as f:
                        script_phase_status = json.load(f)
                    logger.info(f"Read script phase status: {script_phase_status}")
                    update_status(
                        args.status_file, 
                        script_phase_status.get("status", "processing"),
                        script_phase_status.get("message", "Generating script..."),
                        script_phase_status.get("progress", 10), # Default progress if not found
                        "script"
                    )
                except json.JSONDecodeError as e:
                    logger.warning(f"Could not decode JSON from script status file {script_status_file}: {e}. File might be partially written.")
                except Exception as e:
                    logger.warning(f"Error reading or processing script status file {script_status_file}: {e}")
            elif args.status_file:
                logger.info("Script status file not yet available or not used. Waiting.")
            time.sleep(1)
        logger.info("Script process polling loop finished.")
        
        logger.info("Waiting for script process to communicate stdout/stderr...")
        stdout, stderr = script_process.communicate()
        logger.info(f"Script process stdout:\n{stdout}")
        if stderr:
            logger.error(f"Script process stderr:\n{stderr}")
        
        logger.info(f"Script generation process completed with return code: {script_process.returncode}")
        if script_process.returncode != 0:
            error_message = f"Script generation failed. Stderr: {stderr.strip()}"
            logger.error(error_message)
            if args.status_file:
                update_status(args.status_file, "failed", error_message, overall_status.get("script", {}).get("progress", 0), "script")
            return
        
        logger.info(f"Script generated successfully at {args.output_script}")
        if args.status_file:
            update_status(args.status_file, "completed", f"Script generated at {args.output_script}", 100, "script")
            logger.info("Script phase completed. Initializing audio phase status.")
            update_status(args.status_file, "processing", "Initializing audio generation", 0, "audio")
        
        # Step 2: Generate audio
        logger.info("=== Starting Step 2: Convert script to audio ===")
        audio_cmd = [
            sys.executable, 
            "generate_audio.py", 
            "--language", args.language,
            "--input-script", args.output_script,
            "--output-podcast", args.output_podcast
        ]
        # Note: generate_audio.py does not currently support a status file argument.
        # Progress for audio is tracked by parsing stdout.

        logger.info(f"Audio generation command: {' '.join(audio_cmd)}")
        logger.info("Starting audio generation subprocess...")
        audio_process = subprocess.Popen(
            audio_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            bufsize=1, # Line buffered
            universal_newlines=True # Ensures text mode for readline
        )
        logger.info(f"Audio generation subprocess started (PID: {audio_process.pid}).")
        
        logger.info("Monitoring audio generation progress from stdout...")
        # Track progress based on output messages
        # Ensure we read all lines even after process ends for final messages
        audio_lines_processed = []
        while True:
            if audio_process.stdout:
                line = audio_process.stdout.readline()
                if line:
                    line = line.strip()
                    audio_lines_processed.append(line)
                    logger.info(f"Audio process stdout: {line}")
                    if args.status_file:
                        if "Processing Speaker A" in line or "Generating audio for Speaker A" in line: # Adjusted for generate_audio.py logs
                            update_status(args.status_file, "processing", "Generating host voice audio", 30, "audio")
                        elif "Processing Speaker B" in line or "Generating audio for Speaker B" in line:
                            update_status(args.status_file, "processing", "Generating guest voice audio", 60, "audio")
                        elif "Processing Speaker C" in line or "Generating audio for Speaker C" in line:
                            update_status(args.status_file, "processing", "Generating additional voice audio", 80, "audio")
                        elif "Audio segments combined successfully" in line: # Example of a completion message
                            update_status(args.status_file, "processing", "Finalizing audio", 95, "audio")
                elif audio_process.poll() is not None:
                    logger.info("Audio process has ended and no more stdout.")
                    break # Process ended and no more output
            else: # stdout is None, process likely not started correctly or closed.
                if audio_process.poll() is not None:
                    logger.info("Audio process has ended and stdout was None.")
                    break
            time.sleep(0.1) # Short sleep to avoid busy-waiting

        logger.info("Audio process stdout monitoring loop finished.")
        
        logger.info("Waiting for audio process to communicate remaining stdout/stderr...")
        # stdout_audio, stderr_audio = audio_process.communicate() # communicate can only be called once
        # stdout was already read line by line. stderr needs to be read.
        stderr_audio = ""
        if audio_process.stderr:
            stderr_audio = audio_process.stderr.read()

        logger.info(f"Remaining audio process stdout (already processed line-by-line usually):\n{''.join(audio_lines_processed)}")
        if stderr_audio:
            logger.error(f"Audio process stderr:\n{stderr_audio}")

        logger.info(f"Audio generation process completed with return code: {audio_process.returncode}")
        if audio_process.returncode != 0:
            error_message = f"Audio generation failed. Stderr: {stderr_audio.strip()}"
            logger.error(error_message)
            if args.status_file:
                update_status(args.status_file, "failed", error_message, overall_status.get("audio", {}).get("progress", 0), "audio")
            return
        
        logger.info(f"Checking for output podcast file: {args.output_podcast}")
        if os.path.exists(args.output_podcast) and os.path.getsize(args.output_podcast) > 0:
            logger.info(f"Podcast generation complete! Output: {args.output_podcast}")
            if args.status_file:
                update_status(args.status_file, "completed", f"Podcast generated: {args.output_podcast}", 100, "audio")
        else:
            error_message = f"Failed to generate final podcast audio or file is empty at {args.output_podcast}. Stderr: {stderr_audio.strip()}"
            logger.error(error_message)
            if args.status_file:
                update_status(args.status_file, "failed", error_message, 98, "audio") # Mark as almost complete but failed
            
    except subprocess.CalledProcessError as e:
        logger.error(f"A subprocess failed: {e.cmd}, Return code: {e.returncode}, Output: {e.output}, Stderr: {e.stderr}")
        if args.status_file:
            update_status(args.status_file, "failed", f"Subprocess error: {str(e)}", 0, "overall_process")
    except FileNotFoundError as e:
        logger.error(f"File not found error: {str(e)}. This might be due to an incorrect command or missing script.")
        if args.status_file:
            update_status(args.status_file, "failed", f"File not found: {str(e)}", 0, "overall_process")
    except Exception as e:
        logger.error(f"An unexpected error occurred in generate_podcast: {str(e)}", exc_info=True)
        if args.status_file:
            update_status(args.status_file, "failed", f"Unexpected error: {str(e)}", 0, "overall_process")
    finally:
        logger.info("generate_podcast function finished.")

if __name__ == "__main__":
    logger.info("generate_podcast.py script execution started as __main__.")
    args = parse_arguments()
    logger.info(f"Calling generate_podcast with args: {args}")
    generate_podcast(args)
    logger.info("generate_podcast.py script execution finished.")
