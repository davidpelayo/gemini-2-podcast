# generate_audio.py

import tempfile
import asyncio
import os
from audio_processor import AudioGenerator
from dotenv import load_dotenv
from pydub import AudioSegment
import argparse
import re
import logging
import datetime
from pathlib import Path

load_dotenv()

# === Configure logging ===
# Create logs directory if it doesn't exist
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Define log filename with timestamp
log_filename = logs_dir / f"generate_audio_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s')
logger = logging.getLogger(__name__)

# Add file handler
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
logger.addHandler(file_handler)

logger.info(f"Logging to file: {log_filename}")

VOICE_A = os.getenv('VOICE_A', 'Puck')
VOICE_B = os.getenv('VOICE_B', 'Kore')
VOICE_C = os.getenv('VOICE_C', 'Charon')
logger.info(f"Voices set: VOICE_A='{VOICE_A}', VOICE_B='{VOICE_B}', VOICE_C='{VOICE_C}'")

def parse_audio_args():
    logger.info("Parsing command-line arguments for audio generation.")
    parser = argparse.ArgumentParser(description="Generate audio from script.")
    parser.add_argument('--language', default='English', help='Language for audio narration')
    parser.add_argument('--input-script', default='podcast_script.txt', help='Path to the input script file')
    parser.add_argument('--output-podcast', default='final_podcast.wav', help='Path for the output podcast audio file')
    args = parser.parse_args()
    logger.info(f"Arguments parsed: Language='{args.language}', InputScript='{args.input_script}', OutputPodcast='{args.output_podcast}'")
    return args

def parse_conversation(file_path):
    logger.info(f"Parsing conversation from file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.debug(f"Successfully read content from {file_path}. Length: {len(content)}")
    except FileNotFoundError:
        logger.error(f"Error: Script file not found at path: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading script file {file_path}: {str(e)}")
        raise

    lines = content.strip().split('\n')
    logger.debug(f"Total lines in script: {len(lines)}")
    speaker_a_lines = []
    speaker_b_lines = []
    speaker_c_lines = []
    for index, line in enumerate(lines, start=0): # Start index from 0 for filename consistency
        if line.strip():
            if line.startswith("Speaker A:"):
                speaker_a_lines.append(line.replace("Speaker A:", f"{index}|").strip())
                logger.debug(f"Added line for Speaker A (original index {index}): {speaker_a_lines[-1]}")
            elif line.startswith("Speaker B:"):
                speaker_b_lines.append(line.replace("Speaker B:", f"{index}|").strip())
                logger.debug(f"Added line for Speaker B (original index {index}): {speaker_b_lines[-1]}")
            elif line.startswith("Speaker C:"):
                speaker_c_lines.append(line.replace("Speaker C:", f"{index}|").strip())
                logger.debug(f"Added line for Speaker C (original index {index}): {speaker_c_lines[-1]}")
            else:
                logger.warning(f"Line {index+1} does not start with a known speaker prefix: '{line[:30]}...'")


    logger.info(f"Parsed conversation: Speaker A lines: {len(speaker_a_lines)}, Speaker B lines: {len(speaker_b_lines)}, Speaker C lines: {len(speaker_c_lines)}")
    return speaker_a_lines, speaker_b_lines, speaker_c_lines

def read_file_content(file_path):
    logger.info(f"Reading content from file: {file_path}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        logger.info(f"Successfully read content from {file_path}. Length: {len(content)}")
        return content
    except FileNotFoundError:
        logger.error(f"Error: File not found at path: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Error reading file {file_path}: {str(e)}")
        raise

async def setup_environment():
    logger.info("Setting up environment.")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logger.info(f"Script directory: {script_dir}")
    return script_dir

def read_and_parse_inputs(input_script_path):
    logger.info(f"Reading and parsing inputs. Input script: {input_script_path}")
    system_instructions_path = 'system_instructions_audio.txt'
    logger.info(f"Reading system instructions from: {system_instructions_path}")
    system_instructions = read_file_content(system_instructions_path)
    
    logger.info(f"Reading full script from: {input_script_path}")
    full_script = read_file_content(input_script_path)
    
    logger.info(f"Parsing conversation from: {input_script_path}")
    speaker_a_lines, speaker_b_lines, speaker_c_lines = parse_conversation(input_script_path)
    
    logger.info("Finished reading and parsing inputs.")
    return system_instructions, full_script, speaker_a_lines, speaker_b_lines, speaker_c_lines

def prepare_speaker_dialogues(system_instructions, full_script, speaker_lines, voice, temp_dir):
    logger.info(f"Preparing dialogues for voice: {voice} in temp_dir: {temp_dir}")
    logger.debug(f"Number of speaker lines for {voice}: {len(speaker_lines)}")

    dialogues = [system_instructions + "\n\n" + full_script]
    initial_filename = f"speaker_{voice}_initial.wav"
    output_files = [os.path.join(temp_dir, initial_filename)]
    logger.debug(f"Initial dialogue (full script context) prepared for {voice}. Output file: {initial_filename}")

    for i, line_with_num in enumerate(speaker_lines):
        line_num, line_dialog = get_line_number(line_with_num)
        if line_num is None:
            logger.warning(f"Could not extract line number from: '{line_with_num}'. Skipping this line for {voice}.")
            continue
        dialogues.append(line_dialog)
        filename = f"{line_num}_speaker_{voice}.wav"
        output_files.append(os.path.join(temp_dir, filename))
        logger.debug(f"Prepared dialogue for {voice} (line {line_num}): '{line_dialog[:50]}...'. Output file: {filename}")
    
    logger.info(f"Prepared {len(dialogues)} dialogues and {len(output_files)} output file paths for voice: {voice}")
    return dialogues, output_files

def get_line_number(line):
    logger.debug(f"Attempting to get line number from: '{line}'")
    match = re.match(r"(\d+)\|(.*)", line)
    if match:
        line_num = int(match.group(1))
        dialogue = match.group(2).strip()
        logger.debug(f"Extracted line number: {line_num}, dialogue: '{dialogue[:50]}...'")
        return line_num, dialogue
    logger.warning(f"No line number pattern found in: '{line}'")
    return None, line # Return None for line_num if not found

async def process_speaker(voice, dialogues, output_files, language_name="english"):
    logger.info(f"Processing speaker: {voice}, Language: {language_name}. Dialogues: {len(dialogues)}, Output files: {len(output_files)}")
    if not dialogues or not output_files:
        logger.warning(f"No dialogues or output files for speaker {voice}. Skipping processing.")
        return

    generator = AudioGenerator(voice, language_name=language_name)
    logger.info(f"AudioGenerator created for {voice}.")
    
    logger.info(f"Starting batch processing for {voice}...")
    await generator.process_batch(dialogues, output_files)
    logger.info(f"Batch processing completed for {voice}.")

    if generator.ws:
        logger.info(f"Closing websocket connection for {voice}.")
        await generator.ws.close()
        logger.info(f"Websocket connection closed for {voice}.")
    else:
        logger.info(f"No active websocket connection to close for {voice}.")
    logger.info(f"Finished processing for speaker: {voice}")
        
def extract_line_num(filename):
    logger.debug(f"Extracting line number from filename: {filename}")
    match = re.search(r"(\d+)_speaker_.*\.wav", filename)
    if match:
        num = int(match.group(1))
        logger.debug(f"Extracted line number {num} from {filename}")
        return num
    logger.warning(f"Could not extract line number from {filename}, returning float('inf') for sorting.")
    return float('inf') # Should not happen if filenames are correct

def interleave_output_files(speaker_a_files, speaker_b_files, speaker_c_files):
    logger.info("Interleaving output files from all speakers.")
    logger.debug(f"Speaker A files: {len(speaker_a_files)}, Speaker B files: {len(speaker_b_files)}, Speaker C files: {len(speaker_c_files)}")
    
    all_files = speaker_a_files + speaker_b_files + speaker_c_files
    logger.info(f"Total files to interleave: {len(all_files)}")
    logger.debug(f"Files before sorting: {all_files}")
    
    all_files.sort(key=extract_line_num)
    logger.info(f"Files sorted for interleaving. Count: {len(all_files)}")
    logger.debug(f"Files after sorting: {all_files}")
    return all_files

def combine_audio_files(file_list, output_file, silence_duration_ms=50):
    logger.info(f"Combining {len(file_list)} audio files into {output_file} with {silence_duration_ms}ms silence.")
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=silence_duration_ms)
    logger.debug(f"Created silence segment of {silence_duration_ms}ms.")

    for i, file_path in enumerate(file_list):
        logger.debug(f"Processing file {i+1}/{len(file_list)}: {file_path}")
        try:
            audio = AudioSegment.from_wav(file_path)
            if audio.channels == 1:
                logger.debug(f"Audio file {file_path} is mono, converting to stereo.")
                audio = audio.set_channels(2)
            combined += audio + silence
            logger.debug(f"Added {file_path} to combined audio.")
        except Exception as e:
            logger.error(f"Error processing audio file {file_path}: {e}. Skipping this file.")
            continue


    logger.info(f"Exporting combined audio to {output_file}")
    try:
        combined.export(output_file, format="wav")
        logger.info(f"Successfully exported combined audio to {output_file}")
    except Exception as e:
        logger.error(f"Failed to export combined audio to {output_file}: {e}")
        raise

async def main():
    logger.info("Starting main execution of generate_audio.py")
    audio_args = parse_audio_args()
    language = audio_args.language
    input_script_path = audio_args.input_script
    output_podcast_path = audio_args.output_podcast

    logger.info("Setting up script environment.")
    script_dir = await setup_environment()
    logger.info(f"Script environment setup. Using directory: {script_dir}")

    with tempfile.TemporaryDirectory(dir=script_dir) as temp_dir:
        logger.info(f"Created temporary directory: {temp_dir}")
        
        system_instructions, full_script, speaker_a_lines, speaker_b_lines, speaker_c_lines = read_and_parse_inputs(input_script_path)

        logger.info("Preparing dialogues for Speaker A.")
        dialogues_a, output_files_a = prepare_speaker_dialogues(
            system_instructions, full_script, speaker_a_lines, VOICE_A, temp_dir)
        
        logger.info("Preparing dialogues for Speaker B.")
        dialogues_b, output_files_b = prepare_speaker_dialogues(
            system_instructions, full_script, speaker_b_lines, VOICE_B, temp_dir)

        logger.info("Preparing dialogues for Speaker C.")
        dialogues_c, output_files_c = prepare_speaker_dialogues(
            system_instructions, full_script, speaker_c_lines, VOICE_C, temp_dir)

        logger.info(f"Processing Speaker A ({VOICE_A})...")
        await process_speaker(VOICE_A, dialogues_a, output_files_a, language_name=language)
        
        logger.info(f"Processing Speaker B ({VOICE_B})...")
        await process_speaker(VOICE_B, dialogues_b, output_files_b, language_name=language)
        
        logger.info(f"Processing Speaker C ({VOICE_C})...")
        await process_speaker(VOICE_C, dialogues_c, output_files_c, language_name=language)

        # We skip the first file in each list as it's the initial context audio, not part of the dialogue
        logger.info("Interleaving individual speaker audio files (excluding initial context files).")
        all_output_files = interleave_output_files(output_files_a[1:], output_files_b[1:], output_files_c[1:])
        
        logger.info(f"Combining {len(all_output_files)} audio segments into final podcast.")
        combine_audio_files(all_output_files, output_podcast_path, silence_duration_ms=50)
        logger.info(f"Final podcast audio created: {output_podcast_path}")

    logger.info(f"Temporary directory {temp_dir} and its contents have been removed.")
    logger.info("generate_audio.py execution finished successfully.")

if __name__ == "__main__":
    logger.info("generate_audio.py executed as main script.")
    try:
        asyncio.run(main())
    except Exception as e:
        logger.critical(f"An unhandled exception occurred in main: {e}", exc_info=True)
