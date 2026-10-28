"""AI Voice Narration Synthesizer.
Supports studio-quality Neural AI voices across 13+ languages using Edge-TTS,
with offline fallback to pyttsx3.
"""
import os
import asyncio
import hashlib
from pathlib import Path

# High-quality neural voices mapping for each language
NEURAL_VOICES = {
    "en": "en-US-ChristopherNeural",   # English (US) - Deep, clear male
    "hi": "hi-IN-MadhurNeural",        # Hindi (India) - Natural male
    "ta": "ta-IN-ValluvarNeural",      # Tamil (India) - Clear male
    "te": "te-IN-MohanNeural",         # Telugu (India) - Natural male
    "kn": "kn-IN-GaganNeural",         # Kannada (India) - Clear male
    "ml": "ml-IN-MidhunNeural",        # Malayalam (India) - Clear male
    "bn": "bn-IN-BashkarNeural",       # Bengali (India) - Natural male
    "mr": "mr-IN-ManoharNeural",       # Marathi (India) - Natural male
    "gu": "gu-IN-NiranjanNeural",      # Gujarati (India) - Natural male
    "es": "es-ES-AlvaroNeural",        # Spanish (Spain) - Natural male
    "fr": "fr-FR-HenriNeural",         # French (France) - Natural male
    "de": "de-DE-ConradNeural",        # German (Germany) - Natural male
    "ja": "ja-JP-KeitaNeural",         # Japanese (Japan) - Natural male
}

# Alternate female voices for customization
FEMALE_VOICES = {
    "en": "en-US-JennyNeural",
    "hi": "hi-IN-SwaraNeural",
    "ta": "ta-IN-PallaviNeural",
    "te": "te-IN-ShrutiNeural",
    "kn": "kn-IN-SapnaNeural",
    "ml": "ml-IN-SobhanaNeural",
    "bn": "bn-IN-TanishaaNeural",
    "mr": "mr-IN-AarohiNeural",
    "gu": "gu-IN-DhwaniNeural",
    "es": "es-ES-ElviraNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "ja": "ja-JP-NanamiNeural",
}

LANGUAGE_NAMES = {
    "en": "English", "hi": "Hindi (हिन्दी)", "ta": "Tamil (தமிழ்)",
    "te": "Telugu (తెలుగు)", "kn": "Kannada (ಕನ್ನಡ)", "ml": "Malayalam (മലയാളം)",
    "bn": "Bengali (বাংলা)", "mr": "Marathi (मराठी)", "gu": "Gujarati (ગુજરાતી)",
    "es": "Spanish (Español)", "fr": "French (Français)", "de": "German (Deutsch)",
    "ja": "Japanese (日本語)"
}

async def _synthesize_edge_tts(text: str, output_path: str, voice: str) -> bool:
    try:
        import edge_tts
        comm = edge_tts.Communicate(text, voice)
        await comm.save(output_path)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 500
    except Exception as exc:
        return False

def synthesize(text: str, output_path: str, language: str = "en", gender: str = "male") -> tuple[bool, str]:
    """Synthesize speech using Neural AI voice (edge-tts) or fallback to pyttsx3."""
    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)

    voice_map = FEMALE_VOICES if gender.lower() == "female" else NEURAL_VOICES
    voice = voice_map.get(language, NEURAL_VOICES.get("en", "en-US-ChristopherNeural"))

    # Attempt Neural AI synthesis
    try:
        # If output_path was .wav, we can write .mp3 directly or let edge_tts write
        mp3_target = str(out_file.with_suffix(".mp3"))
        
        # Run async in event loop safely
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Running loop inside FastAPI, create task or new loop in thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    success = pool.submit(lambda: asyncio.run(_synthesize_edge_tts(text, mp3_target, voice))).result(timeout=15)
            else:
                success = loop.run_until_complete(_synthesize_edge_tts(text, mp3_target, voice))
        except RuntimeError:
            success = asyncio.run(_synthesize_edge_tts(text, mp3_target, voice))

        if success:
            # If the caller specifically needed the original output_path (e.g. .wav), copy or keep mp3
            if str(out_file) != mp3_target and not out_file.exists():
                import shutil
                shutil.copyfile(mp3_target, str(out_file))
            return True, f"Neural AI Voice ({voice})"
    except Exception as exc:
        pass

    # Offline Fallback to pyttsx3
    try:
        import pyttsx3
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        wanted = {"en": ("en", "english"), "hi": ("hi", "hindi"), "ta": ("ta", "tamil")}.get(language, ("en",))
        for v in voices:
            details = f"{getattr(v, 'id', '')} {getattr(v, 'name', '')}".lower()
            if any(token in details for token in wanted):
                engine.setProperty("voice", v.id)
                break
        engine.save_to_file(text, str(out_file))
        engine.runAndWait()
        if os.path.exists(output_path) and os.path.getsize(output_path) > 1000:
            return True, f"Local pyttsx3 fallback ({language})"
    except Exception as exc:
        return False, f"TTS synthesis unavailable: {exc}"

    return False, "No usable TTS voice found"
