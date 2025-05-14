# audio_processor.py

import asyncio
import base64
import json
import os
import wave
from websockets.asyncio.client import connect
import websockets
import pyaudio
from dotenv import load_dotenv
import sys
import logging

load_dotenv()

# Configure logging
logger = logging.getLogger(__name__)
# Example basic configuration (ideally done at application entry point)
# logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


GOOGLE_API_KEY = os.getenv('GOOGLE_API_KEY')
if not GOOGLE_API_KEY:
    logger.warning("GOOGLE_API_KEY environment variable not set.")

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

if sys.version_info < (3, 11):
    logger.info("Python version < 3.11, importing taskgroup and exceptiongroup polyfills.")
    import taskgroup, exceptiongroup
    asyncio.TaskGroup = taskgroup.TaskGroup
    asyncio.ExceptionGroup = exceptiongroup.ExceptionGroup

class AudioGenerator:
    def __init__(self, voice, language_name="english"):
        logger.info(f"Initializing AudioGenerator with voice: {voice}, language_name: {language_name}")
        self.voice = voice
        self.language_code = LANGUAGE_CODE_MAP.get(language_name.lower(), DEFAULT_LANGUAGE_CODE)
        logger.info(f"Using language code: {self.language_code} for language: {language_name}")
        self.audio_in_queue = asyncio.Queue()
        self.ws = None
        self.ws_semaphore = asyncio.Semaphore(1) # Semaphore to protect WebSocket operations if needed, though typically one operation at a time.

        # Audio configuration
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 2 # Outputting stereo
        self.SAMPLE_RATE = 24000
        self.CHUNK_SIZE = 512
        logger.debug(f"Audio config: FORMAT={self.FORMAT}, CHANNELS={self.CHANNELS}, SAMPLE_RATE={self.SAMPLE_RATE}, CHUNK_SIZE={self.CHUNK_SIZE}")

        # WebSocket configuration
        self.ws_options = {
            'ping_interval': 10,
            'ping_timeout': 7,
            'close_timeout': 5
        }
        logger.debug(f"WebSocket options: {self.ws_options}")

        # API configuration
        self.host = 'generativelanguage.googleapis.com'
        self.model = "gemini-2.0-flash-live-001" # Using a specific model version
        if GOOGLE_API_KEY:
            self.uri = f"wss://{self.host}/ws/google.ai.generativelanguage.v1beta.GenerativeService.BidiGenerateContent?key={GOOGLE_API_KEY}"
            logger.info(f"Using API URI for host: {self.host} and model: {self.model}")
        else:
            self.uri = None
            logger.error("GOOGLE_API_KEY is not set. Cannot form API URI.")


        self.complete_audio = bytearray()
        logger.info("AudioGenerator initialized successfully.")

    async def cleanup(self):
        logger.info("Starting AudioGenerator cleanup.")
        if self.ws and not self.ws.closed:
            logger.info("Closing WebSocket connection.")
            try:
                await self.ws.close()
                logger.info("WebSocket connection closed.")
            except Exception as e:
                logger.error(f"Error closing WebSocket: {e}", exc_info=True)
        else:
            logger.info("WebSocket connection already closed or not established.")
        
        self.complete_audio.clear()
        logger.debug("Cleared complete_audio buffer.")
        
        if not self.audio_in_queue.empty():
            logger.debug(f"Clearing audio_in_queue (size: {self.audio_in_queue.qsize()}).")
            while not self.audio_in_queue.empty():
                self.audio_in_queue.get_nowait()
            logger.debug("audio_in_queue cleared.")
        logger.info("AudioGenerator cleanup finished.")

    async def process_batch(self, dialogues, output_files):
        logger.info(f"Starting process_batch for {len(dialogues)} dialogues.")
        if not self.uri:
            logger.error("Cannot process batch: API URI is not set (GOOGLE_API_KEY missing).")
            return

        try:
            logger.debug(f"Attempting to connect to WebSocket: {self.uri.split('?')[0]}...") # Avoid logging key
            ws = await connect(self.uri, **self.ws_options)
            async with ws:
                self.ws = ws
                logger.info("WebSocket connection established for process_batch.")
                await self.startup(ws, self.voice)
                for i, (dialogue, output_file) in enumerate(zip(dialogues, output_files)):
                    logger.info(f"Processing dialogue {i+1}/{len(dialogues)} for output file: {output_file}")
                    await self.send_text(ws, dialogue)
                    await self.receive_audio(output_file)
                logger.info("process_batch completed successfully.")
        except websockets.exceptions.InvalidURI:
            logger.error(f"Invalid WebSocket URI: {self.uri.split('?')[0]}. Check API key and endpoint.", exc_info=True)
        except websockets.exceptions.WebSocketException as e:
            logger.error(f"WebSocket exception during process_batch: {e}", exc_info=True)
        except Exception as e:
            logger.error(f"Unexpected error during process_batch: {e}", exc_info=True)
        finally:
            if self.ws and not self.ws.closed:
                logger.debug("Ensuring WebSocket is closed at the end of process_batch.")
                await self.ws.close()
            self.ws = None # Reset ws instance

    async def startup(self, ws, voice):
        logger.info(f"Starting WebSocket session with voice: {voice}, language: {self.language_code}")
        async with self.ws_semaphore: # Ensure exclusive access if ws object is shared, though here it's passed
            logger.debug("Acquired ws_semaphore for startup.")
            setup_msg = {
                "setup": {
                    "model": f"models/{self.model}",
                    "generation_config": {
                        "speech_config": {
                            "language_code": self.language_code,
                            "voice_config": {
                                "prebuilt_voice_config": {
                                    "voice_name": voice
                                }
                            }
                        }
                    }
                }
            }
            logger.debug(f"Sending setup message: {json.dumps(setup_msg)}")
            await ws.send(json.dumps(setup_msg))
            logger.info("Setup message sent. Waiting for server response...")
            response_raw = await ws.recv()
            logger.debug(f"Received startup response: {response_raw}")
            # You might want to handle this response, e.g., check for errors
            try:
                response_json = json.loads(response_raw)
                if response_json.get("serverContent", {}).get("setupComplete"):
                     logger.info("Server confirmed setup complete.")
                else:
                     logger.warning(f"Unexpected startup response content: {response_json}")
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from startup response: {response_raw}")
            logger.debug("Released ws_semaphore after startup.")


    async def send_text(self, ws, text):
        logger.info(f"Sending text (length: {len(text)}) to WebSocket.")
        logger.debug(f"Text preview (first 100 chars): {text[:100]}")
        async with self.ws_semaphore:
            logger.debug("Acquired ws_semaphore for send_text.")
            msg = {
                "client_content": {
                    "turn_complete": True,
                    "turns": [
                        {"role": "user", "parts": [{"text": text}]}
                    ]
                }
            }
            logger.debug(f"Sending text message: {json.dumps(msg)}")
            await ws.send(json.dumps(msg))
            logger.info("Text message sent.")
            logger.debug("Released ws_semaphore after send_text.")

    async def receive_audio(self, output_file):
        logger.info(f"Starting to receive audio for output file: {output_file}")
        async with self.ws_semaphore: # Protects self.complete_audio and self.audio_in_queue
            logger.debug("Acquired ws_semaphore for receive_audio.")
            self.complete_audio.clear()
            logger.debug("Cleared complete_audio buffer for new audio stream.")
            
            # Small delay to ensure the server has processed the text and is ready to send audio
            await asyncio.sleep(0.1) 
            logger.debug("Waited 0.1s, now listening for audio data.")

            try:
                async for raw_response in self.ws:
                    logger.debug(f"Received raw response (length: {len(raw_response)})")
                    response = json.loads(raw_response)
                    logger.debug(f"Parsed JSON response: {response if len(str(response)) < 500 else str(response)[:500] + '...'}")


                    try:
                        parts = response["serverContent"]["modelTurn"]["parts"]
                        for part_idx, part in enumerate(parts):
                            if "inlineData" in part:
                                b64data = part["inlineData"]["data"]
                                pcm_data = base64.b64decode(b64data)
                                self.complete_audio.extend(pcm_data)
                                self.audio_in_queue.put_nowait(pcm_data)
                                logger.debug(f"Received audio data chunk {part_idx + 1} (PCM size: {len(pcm_data)} bytes). Total collected: {len(self.complete_audio)} bytes.")
                            # else:
                            #     logger.debug(f"Part {part_idx+1} does not contain inlineData: {part}")
                    except KeyError:
                        logger.debug("KeyError: 'serverContent' or 'modelTurn' or 'parts' not in response, or part structure unexpected. Skipping audio processing for this message.")
                        # logger.debug(f"Full response causing KeyError: {response}")


                    try:
                        if response["serverContent"].get("turnComplete", False):
                            logger.info(f"Turn complete signal received. Total audio data received: {len(self.complete_audio)} bytes.")
                            self.save_wav_file(output_file)
                            logger.debug(f"Clearing audio_in_queue (size: {self.audio_in_queue.qsize()}) after saving file.")
                            while not self.audio_in_queue.empty():
                                self.audio_in_queue.get_nowait()
                            logger.debug("audio_in_queue cleared. Breaking from receive loop.")
                            break
                    except KeyError:
                        logger.debug("KeyError: 'serverContent' or 'turnComplete' not in response. Continuing to listen.")
                        # logger.debug(f"Full response causing KeyError: {response}")


            except websockets.exceptions.ConnectionClosedError as e:
                logger.error(f"WebSocket connection closed unexpectedly during audio reception: {e}", exc_info=True)
                raise # Re-raise to be handled by the caller (e.g., run method's retry logic)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON from WebSocket message: {raw_response}, error: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Unexpected error during audio reception: {e}", exc_info=True)
                raise
            finally:
                logger.debug("Released ws_semaphore after receive_audio.")
        logger.info(f"Finished receiving audio for {output_file}.")


    def save_wav_file(self, filename):
        logger.info(f"Saving complete audio to WAV file: {filename}")
        if not self.complete_audio:
            logger.warning(f"No audio data in complete_audio buffer to save for {filename}. Skipping save.")
            return

        try:
            with wave.open(filename, 'wb') as wav_file:
                wav_file.setnchannels(self.CHANNELS)
                wav_file.setsampwidth(2)  # 2 bytes for paInt16
                wav_file.setframerate(self.SAMPLE_RATE)
                
                logger.debug(f"Audio parameters for WAV: Channels={self.CHANNELS}, SampWidth=2, FrameRate={self.SAMPLE_RATE}")
                logger.debug(f"Length of mono complete_audio: {len(self.complete_audio)} bytes.")

                # Assuming self.complete_audio is mono, convert to stereo by duplicating samples
                stereo_data = bytearray()
                if self.CHANNELS == 1: # If source is mono and output is mono
                    stereo_data = self.complete_audio
                elif self.CHANNELS == 2: # If source is mono and output is stereo
                    for i in range(0, len(self.complete_audio), 2): # Assuming 2 bytes per sample (16-bit)
                        sample = self.complete_audio[i:i+2]
                        stereo_data.extend(sample) # Left channel
                        stereo_data.extend(sample) # Right channel (duplicate)
                else:
                    logger.error(f"Unsupported channel configuration: self.CHANNELS = {self.CHANNELS}. Saving as is.")
                    stereo_data = self.complete_audio # Fallback or handle error

                logger.debug(f"Length of stereo_data to write: {len(stereo_data)} bytes.")
                wav_file.writeframes(stereo_data)
                logger.info(f"Successfully saved WAV file: {filename} ({len(stereo_data)} bytes written)")
        except Exception as e:
            logger.error(f"Error saving WAV file {filename}: {e}", exc_info=True)


    async def run(self, dialogues, output_files, max_retries=3):
        logger.info(f"Starting run method for {len(dialogues)} dialogues with max_retries={max_retries}.")
        if not self.uri:
            logger.error("Cannot run: API URI is not set (GOOGLE_API_KEY missing). Aborting.")
            return

        last_exception = None
        for attempt in range(max_retries):
            logger.info(f"Attempt {attempt + 1}/{max_retries} to process dialogues.")
            try:
                logger.debug(f"Attempting to connect to WebSocket: {self.uri.split('?')[0]}...") # Avoid logging key
                ws = await connect(self.uri, **self.ws_options)
                async with ws: # Ensures ws.close() is called on exit
                    self.ws = ws # Store the active WebSocket connection
                    logger.info(f"WebSocket connection established for attempt {attempt + 1}.")
                    
                    await self.startup(self.ws, self.voice)
                    
                    for i, (dialogue, output_file) in enumerate(zip(dialogues, output_files)):
                        logger.info(f"Processing dialogue {i+1}/{len(dialogues)} (file: {output_file}) on attempt {attempt + 1}.")
                        await self.send_text(self.ws, dialogue)
                        await self.receive_audio(output_file) # This method now handles its own semaphore for internal state
                        logger.info(f"Successfully processed dialogue {i+1}/{len(dialogues)} for {output_file}.")
                
                logger.info("All dialogues processed successfully in this attempt.")
                self.ws = None # Clear ws instance as it's closed by async with
                return # Successful completion
            
            except websockets.exceptions.InvalidURI as e:
                logger.error(f"Invalid WebSocket URI: {self.uri.split('?')[0]}. Cannot connect. Aborting retries.", exc_info=True)
                last_exception = e
                break # No point retrying if URI is bad
            except websockets.exceptions.ConnectionClosedError as e:
                last_exception = e
                logger.warning(f"Connection lost during attempt {attempt + 1}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    wait_time = 5 * (attempt + 1) # Exponential backoff could be considered
                    logger.info(f"Retrying in {wait_time} seconds... (Attempt {attempt + 2}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached. Unable to reconnect after connection loss.")
            except Exception as e: # Catch other potential errors during connection or processing
                last_exception = e
                logger.error(f"An unexpected error occurred during attempt {attempt + 1}: {e}", exc_info=True)
                if attempt < max_retries - 1:
                    wait_time = 5
                    logger.info(f"Retrying in {wait_time} seconds due to unexpected error... (Attempt {attempt + 2}/{max_retries})")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("Max retries reached. Unable to complete due to unexpected errors.")
            finally:
                if self.ws and not self.ws.closed: # Ensure ws is closed if an error occurred before async with exited
                    logger.debug("Ensuring WebSocket is closed in run method's finally block.")
                    await self.ws.close()
                self.ws = None # Reset ws instance

        if last_exception:
            logger.error(f"Failed to process dialogues after {max_retries} attempts.")
            raise last_exception # Re-raise the last encountered exception
