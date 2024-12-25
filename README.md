
# gemini-2-podcast Setup Guide

A Python-based tool that generates engaging podcast conversations using Google's Gemini 2.0 Flash Experimental model for script generation and text-to-speech conversion.

## Features
- Converts content from multiple source formats (PDF, URL, TXT, Markdown) into natural conversational scripts.
- Generates high-quality audio using Google's text-to-speech capabilities.
- Supports two distinct voices for dynamic conversations.
- Handles error recovery and retries for robust audio generation.
- Progress tracking with visual feedback during generation.

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
git clone https://github.com/agituts/gemini-2-podcast.git
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
```

## Required Files
```text
Ensure these files are present in your project directory:
- generate_podcast.py
- generate_script.py
- generate_audio.py
- system_instructions_script.txt
- system_instructions_audio.txt
- requirements.txt
- README.md
```

## Usage Instructions

### Start the Podcast Generation:
```bash
python generate_podcast.py
```

1. When prompted, input content sources:
   ```text
   - PDF files: pdf
   - URLs: url
   - Text files: txt
   - Markdown files: md
   ```
2. Type `done` when finished.
3. Review the generated script in `podcast_script.txt`.
4. Press `Enter` to continue with audio generation or `q` to quit.

### Wait for Audio Generation to Complete:
```text
- A progress bar will display the status.
- Final output: final_podcast.wav.
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
