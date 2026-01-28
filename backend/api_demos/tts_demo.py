# TTS
from google import genai
from google.genai import types
import wave
from pathlib import Path

def wave_file(filename, pcm, channels=1, rate=24000, sample_width=2):
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm)

client = genai.Client()

# EXAMPLE
# IMPORTANT: the prompt must to start with "Say". 
tts_text = (
    "Say: A gunshot cracks through the Blue Note, cutting the music dead. "
    "Smoke curls from a back table, and a man in a fedora bolts for the kitchen door.\n\n"
    "People freeze. No one screams. They’re all pretending they didn’t see.\n\n"
    "You did. He’s getting away. Move."
)


response = client.models.generate_content(
    model="gemini-2.5-flash-preview-tts",
    contents=tts_text,
    config=types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name="Charon",
                )
            )
        ),
    )
)

data = response.candidates[0].content.parts[0].inline_data.data

out_dir = Path("audio_tests")
out_dir.mkdir(parents=True, exist_ok=True)

file_path = out_dir / "narrator_charon.wav"
wave_file(file_path, data)

# ---------
# Outputs
# ---------

# Print Tokens
usage = response.usage_metadata
print(f"Input Tokens:    {usage.prompt_token_count}")
print(f"Thinking Tokens: {usage.thoughts_token_count}")
print(f"Output Tokens:   {usage.candidates_token_count}")
print(f"--------------------------")
print(f"Total Tokens:    {usage.total_token_count}")

# Print Response and stored file
print("Saved:", file_path.resolve())
