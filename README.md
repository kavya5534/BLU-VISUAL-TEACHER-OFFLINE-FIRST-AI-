# Blu Visual Teacher — Offline Hackathon MVP

A local-first starter implementation for the Blu Visual Teacher Hackathon. It turns a typed topic into a short lesson with animated scenes, captions, local narration when configured, and MP4 export through FFmpeg.

## What is included
- Browser UI for topic, learner level, language, and target length.
- FastAPI backend with a strict lesson JSON schema and built-in fallback lesson.
- Optional local Ollama lesson planning (`OLLAMA_MODEL`, default `qwen2.5:3b`).
- Reusable browser scene renderer: title card, code walkthrough, and diagram.
- Playback controls, captions, scene navigation, and replay.
- Local TTS adapter using `pyttsx3` if installed; graceful silent fallback.
- MP4 export using FFmpeg if installed; exports a simple 1280x720 video from rendered SVG scene frames and audio when available.
- English, Hindi, and Tamil UI/lesson fallback content. Translation quality depends on locally installed models; the MVP uses curated fallback strings and does not pretend to provide general-purpose translation.

## Architecture
1. `frontend/` collects input and renders validated JSON scene data.
2. `backend/app.py` validates lesson JSON and uses Ollama only on localhost.
3. `backend/tts.py` generates narration audio locally when `pyttsx3` is available.
4. `backend/exporter.py` invokes local FFmpeg to create an MP4.
5. `data/sample_lessons.json` keeps the demo working if the model or TTS is unavailable.

## Requirements
- Python 3.10+
- Optional: Ollama + a small model (e.g. `ollama pull qwen2.5:3b`)
- Optional: FFmpeg on PATH
- Optional local TTS: `pip install pyttsx3` and a system voice for the selected language

## Run
```bash
python -m venv .venv
# Windows:
.venv\\Scripts\\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
uvicorn backend.app:app --host 127.0.0.1 --port 8000
```
Open http://127.0.0.1:8000

For a model-backed planner:
```bash
ollama pull qwen2.5:3b
# Windows PowerShell:
$env:OLLAMA_MODEL="qwen2.5:3b"
# macOS/Linux:
export OLLAMA_MODEL=qwen2.5:3b
```
The Ollama endpoint is local (`127.0.0.1:11434`) and no external AI APIs are used.

## Export
Use **Export MP4** in the UI. FFmpeg must be installed and available on PATH. If FFmpeg is missing, the UI displays a clear error rather than claiming export succeeded.

## Important limitations to disclose in a hackathon demo
- This is an MVP starter, not a finished production system.
- `pyttsx3` voice availability varies by operating system; verify Hindi/Tamil voices on the actual laptop. For better multilingual narration, integrate licensed local models such as Kokoro for supported languages and AI4Bharat Indic TTS/IndicTrans2 for additional Indian languages.
- The fallback lessons are curated examples, not a universal translation engine.
- Test the full pipeline offline on the exact demo laptop before submission.
- Review model, voice, font, and asset licences and list them in your final submission.

## Suggested 24-hour priority
1. Make the hard-coded sample play end-to-end and export MP4.
2. Verify offline execution and fallback behavior.
3. Test narration and script rendering for all three languages.
4. Improve lesson planning and content correctness.
5. Add voice/speed controls or extra scene types only after the core path is stable.
