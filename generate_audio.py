# generate_audio.py

import tempfile
import asyncio
import os
from audio_processor import AudioGenerator
from dotenv import load_dotenv
from pydub import AudioSegment

load_dotenv()

VOICE_A = os.getenv('VOICE_A', 'Puck')
VOICE_B = os.getenv('VOICE_B', 'Kore')

def parse_conversation(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    lines = content.strip().split('\n')
    speaker_a_lines = []
    speaker_b_lines = []

    for line in lines:
        if line.strip():
            if line.startswith("Speaker A:"):
                speaker_a_lines.append(line.replace("Speaker A:", "").strip())
            elif line.startswith("Speaker B:"):
                speaker_b_lines.append(line.replace("Speaker B:", "").strip())

    return speaker_a_lines, speaker_b_lines

def read_file_content(file_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        return file.read()

async def setup_environment():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    return script_dir

def read_and_parse_inputs():
    system_instructions = read_file_content('system_instructions_audio.txt')
    full_script = read_file_content('podcast_script.txt')
    speaker_a_lines, speaker_b_lines = parse_conversation('podcast_script.txt')
    return system_instructions, full_script, speaker_a_lines, speaker_b_lines

def prepare_speaker_dialogues(system_instructions, full_script, speaker_lines, voice, temp_dir):
    dialogues = [system_instructions + "\n\n" + full_script]
    output_files = [os.path.join(temp_dir, f"speaker_{voice}_initial.wav")]

    for i, line in enumerate(speaker_lines):
        dialogues.append(line)
        output_files.append(os.path.join(temp_dir, f"speaker_{voice}_{i}.wav"))

    return dialogues, output_files

async def process_speaker(voice, dialogues, output_files):
    # Create a single generator for all dialogues
    generator = AudioGenerator(voice)
    
    # Process the entire batch of dialogues at once
    await generator.process_batch(dialogues, output_files)

    # Ensure the websocket connection is closed
    if generator.ws:
        await generator.ws.close()

def interleave_output_files(speaker_a_files, speaker_b_files):
    """Interleaves the audio files from both speakers to maintain conversation order"""
    all_output_files = []
    min_length = min(len(speaker_a_files), len(speaker_b_files))

    # Interleave files from both speakers
    for i in range(min_length):
        all_output_files.extend([speaker_a_files[i], speaker_b_files[i]])

    # Add any remaining files from either speaker
    all_output_files.extend(speaker_a_files[min_length:])
    all_output_files.extend(speaker_b_files[min_length:])

    return all_output_files

def combine_audio_files(file_list, output_file, silence_duration_ms=50):
    combined = AudioSegment.empty()
    silence = AudioSegment.silent(duration=silence_duration_ms)

    for file in file_list:
        audio = AudioSegment.from_wav(file)
        if audio.channels == 1:
            audio = audio.set_channels(2)
        combined += audio + silence

    combined.export(output_file, format="wav")

async def main():
    script_dir = await setup_environment()

    with tempfile.TemporaryDirectory(dir=script_dir) as temp_dir:
        system_instructions, full_script, speaker_a_lines, speaker_b_lines = read_and_parse_inputs()

        # Prepare dialogues for both speakers
        dialogues_a, output_files_a = prepare_speaker_dialogues(
            system_instructions, full_script, speaker_a_lines, VOICE_A, temp_dir)
        dialogues_b, output_files_b = prepare_speaker_dialogues(
            system_instructions, full_script, speaker_b_lines, VOICE_B, temp_dir)

        # Process Speaker A first
        print("Processing Speaker A...")
        await process_speaker(VOICE_A, dialogues_a, output_files_a)
        
        # Then process Speaker B
        print("Processing Speaker B...")
        await process_speaker(VOICE_B, dialogues_b, output_files_b)

        # Interleave and combine audio as before
        all_output_files = interleave_output_files(output_files_a[1:], output_files_b[1:])
        final_output = "final_podcast.wav"
        combine_audio_files(all_output_files, final_output, silence_duration_ms=50)
        print(f"\nFinal podcast audio created: {final_output}")

    print("Temporary files cleaned up")

if __name__ == "__main__":
    asyncio.run(main())
