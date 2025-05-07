# gemini-2-podcast Setup Guide

A Python-based tool that generates engaging podcast conversations using Google's Gemini 2.0 Flash Experimental model for script generation and text-to-speech conversion. Now with multi-language support for generating podcasts in various languages.

[![Gemini 2 Podcast Setup Guide: Transform Content into Pro-Level Podcasts](https://img.youtube.com/vi/9qeiQ4x30Dk/maxresdefault.jpg)](https://www.youtube.com/watch?v=9qeiQ4x30Dk)

## Features
- Converts content from multiple source formats (PDF, URL, TXT, Markdown) into natural conversational scripts.
- Generates high-quality audio using Google's text-to-speech capabilities.
- Supports multiple languages for podcast generation.
- Provides two distinct voices for dynamic conversations.
- Handles error recovery and retries for robust audio generation.
- Progress tracking with visual feedback during generation.
- Non-interactive API for automation and integration.

## Prerequisites

### Microsoft C++ Build Tools
1. Download Microsoft C++ Build Tools from Visual Studio Installer.
2. Run the installer and select:
   - **Desktop development with C++** workload.
   - Optional MSVC build tools (`v140`, `v141`, `v142`) under Installation details.
3. After installation:
   - **Reboot your computer**.
   - Add MSBuild to system environment variables:
     ```text
     C:\Program Files (x86)\Microsoft Visual Studio\2019\BuildTools\MSBuild\Current\Bin
     ```

## System Dependencies

### For Ubuntu/Debian:
```bash
sudo apt-get install ffmpeg portaudio19-dev
```

### For macOS:
```bash
brew install ffmpeg portaudio
```

### For Windows:
```text
Install FFmpeg and add it to PATH
PortAudio comes with PyAudio wheels
```

## Project Setup

### Clone the Repository:
```bash
git clone https://github.com/yourusername/gemini-2-podcast.git
cd gemini-2-podcast
```

### Create and Activate Virtual Environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### Install Python Dependencies:
```bash
pip install -r requirements.txt
```

### Create `.env` File with API Keys:
```text
GOOGLE_API_KEY=your_google_api_key
VOICE_A=Puck
VOICE_B=Kore
VOICE_C=Charon
```

## Required Files
```text
Ensure these files are present in your project directory:
- generate_podcast.py
- generate_script.py
- generate_audio.py
- system_instructions_script_template.txt
- system_instructions_audio_template.txt
- requirements.txt
- README.md
```

## Usage Instructions

### Command-Line API

The podcast generator can be used with the following command-line parameters:

```bash
python generate_podcast.py --source-type <type> --source-path <path> [--language <language>] [--output-script <script_path>] [--output-podcast <podcast_path>]
```

**Required Parameters:**
- `--source-type`: Type of content source (pdf, url, txt, md)
- `--source-path`: Path or URL to the source content

**Optional Parameters:**
- `--language`: Language for audio narration (default: English)
- `--output-script`: Output path for the generated script file (default: podcast_script.txt)
- `--output-podcast`: Output path for the generated podcast audio file (default: final_podcast.wav)

### Examples:

Generate a podcast from a PDF file:
```bash
python generate_podcast.py --source-type pdf --source-path document.pdf
```

Generate a Spanish podcast from a URL:
```bash
python generate_podcast.py --source-type url --source-path https://example.com/article --language Spanish
```

Generate a podcast with custom output paths:
```bash
python generate_podcast.py --source-type txt --source-path content.txt --output-script my_script.txt --output-podcast my_podcast.wav
```

### Using Individual Scripts

You can also use the individual scripts directly:

**Generate script only:**
```bash
python generate_script.py --source-type <type> --source-path <path> --output-script <script_path>
```

**Generate audio from script:**
```bash
python generate_audio.py --input-script <script_path> --output-podcast <podcast_path>
```

## Output Specifications
```text
- Audio format: WAV
- Channels: Stereo
- Sample rate: 24000Hz
- Bit depth: 16-bit
```

## Contributing
1. Fork the repository.
2. Create a feature branch.
3. Commit your changes.
4. Push to the branch.
5. Open a Pull Request.

## License
This project is licensed under the MIT License.

## Acknowledgments
- Inspired by NotebookLM's podcast feature.
