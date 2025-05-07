# generate_audio.py

import os
import argparse
import re
from google.cloud import texttospeech
from dotenv import load_dotenv

load_dotenv()

# Language mapping (moved from audio_processor.py)
LANGUAGE_CODE_MAP = {
    "german": "de-DE",
    "english (australia)": "en-AU",
    "english (uk)": "en-GB",
    "english (india)": "en-IN",
    "english (us)": "en-US",
    "english": "en-US",
    "spanish (us)": "es-US",
    "spanish": "es-ES",
    "french": "fr-FR",
    "hindi": "hi-IN",
    "portuguese": "pt-BR",
    "arabic": "ar-XA",
    "spanish (spain)": "es-ES",
    "french (canada)": "fr-CA",
    "indonesian": "id-ID",
    "italian": "it-IT",
    "japanese": "ja-JP",
    "turkish": "tr-TR",
    "vietnamese": "vi-VN",
    "bengali": "bn-IN",
    "gujarati": "gu-IN",
    "kannada": "kn-IN",
    "malayalam": "ml-IN",
    "marathi": "mr-IN",
    "tamil": "ta-IN",
    "telugu": "te-IN",
    "dutch": "nl-NL",
    "korean": "ko-KR",
    "mandarin": "cmn-CN",
    "chinese": "cmn-CN",
    "polish": "pl-PL",
    "russian": "ru-RU",
    "thai": "th-TH",
}
DEFAULT_LANGUAGE_CODE = "en-US"
MULTI_SPEAKER_VOICE_NAME = "en-US-Studio-MultiSpeaker" # Using a specific multi-speaker voice

SPEAKER_TAG_MAP = {
    "Speaker A": "1",
    "Speaker B": "2",
    "Speaker C": "3",
}

def parse_audio_args():
    parser = argparse.ArgumentParser(description="Generate audio from script using Google Cloud Text-to-Speech.")
    parser.add_argument('--language', default='English', help='Language for audio narration (e.g., English, Italian, Spanish)')
    return parser.parse_args()

def parse_script_for_turns(file_path):
    """Parses the podcast script and converts it into a list of Turn objects for TTS API."""
    turns = []
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    lines = content.strip().split('\\n')
    for line in lines:
        line = line.strip()
        if not line:
            continue

        speaker_tag = None
        text_content = line
        
        for speaker_prefix, tag in SPEAKER_TAG_MAP.items():
            if line.startswith(speaker_prefix + ":"):
                speaker_tag = tag
                text_content = line.replace(speaker_prefix + ":", "", 1).strip()
                break
        
        if speaker_tag and text_content: # Only add if a speaker is identified and there's text
            turns.append(texttospeech.MultiSpeakerMarkup.Turn(text=text_content, speaker=speaker_tag))
        elif text_content: 
            # Handling lines that are not explicitly attributed to Speaker A, B, or C.
            # Option 1: Skip them (current behavior if speaker_tag is None)
            # Option 2: Assign to a default speaker or the last speaker (more complex)
            # Option 3: Raise an error or log a warning.
            # For now, these lines will be skipped if no speaker_tag is found.
            # If all lines *must* have a speaker, the script generation should ensure this.
            print(f"Warning: Line without recognized speaker prefix skipped: '{line}'")


    return turns

def synthesize_multi_speaker_speech(turns, language_code, output_filename):
    """Synthesizes speech from a list of turns using Google Cloud Text-to-Speech."""
    client = texttospeech.TextToSpeechClient()

    multi_speaker_markup = texttospeech.MultiSpeakerMarkup(turns=turns)
    synthesis_input = texttospeech.SynthesisInput(multi_speaker_markup=multi_speaker_markup)

    voice_params = texttospeech.VoiceSelectionParams(
        language_code=language_code,
        name=MULTI_SPEAKER_VOICE_NAME
    )

    # Output WAV format, matching previous project settings (e.g., 24000 Hz)
    # The API defaults to 24000 Hz for LINEAR16 if sample_rate_hertz is not specified.
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.LINEAR16 
    )

    try:
        response = client.synthesize_speech(
            request={"input": synthesis_input, "voice": voice_params, "audio_config": audio_config}
        )
    except Exception as e:
        print(f"Error during TTS API call: {e}")
        print("Please ensure that GOOGLE_APPLICATION_CREDENTIALS environment variable is set correctly and points to a valid service account JSON key file with Text-to-Speech API enabled.")
        raise

    with open(output_filename, "wb") as out:
        out.write(response.audio_content)
    print(f"Audio content written to file \"{output_filename}\"")

def main():
    audio_args = parse_audio_args()
    language_name = audio_args.language.lower()
    language_code = LANGUAGE_CODE_MAP.get(language_name, DEFAULT_LANGUAGE_CODE)

    print(f"Selected language: {language_name}, using BCP-47 code: {language_code}")

    script_file_path = 'podcast_script.txt'
    if not os.path.exists(script_file_path):
        print(f"Error: Script file not found at {script_file_path}")
        return

    turns = parse_script_for_turns(script_file_path)

    if not turns:
        print("No speaker turns found in the script. Cannot generate audio.")
        return

    output_filename = "final_podcast.wav"
    
    synthesize_multi_speaker_speech(turns, language_code, output_filename)
    
    print("Podcast audio generation complete.")

if __name__ == "__main__":
    main()
