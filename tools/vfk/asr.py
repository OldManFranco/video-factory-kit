"""Speech recognition: faster-whisper large-v3 (text + rough times) and wav2vec2 alignment (precise times, via WhisperX).
Runs on the NVIDIA GPU when there is one, otherwise on the CPU (Mac, other PCs: slower)."""
import os

_models = {}


def device():
    """('cuda', 'float16') with an NVIDIA GPU, else ('cpu', 'int8')."""
    if os.environ.get("VFK_DEVICE") == "cpu":
        return "cpu", "int8"
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda", "float16"
    except ImportError:
        pass
    return "cpu", "int8"


def whisper(size="large-v3"):
    if size not in _models:
        import torch  # noqa: F401  (loads the CUDA DLLs on Windows before ctranslate2)
        from faster_whisper import WhisperModel
        dev, ct = device()
        threads = max(1, (os.cpu_count() or 4) - 1)
        _models[size] = WhisperModel(size, device=dev, compute_type=ct, cpu_threads=threads)
    return _models[size]


def aligner(language="en"):
    key = ("align", language)
    if key not in _models:
        import whisperx
        _models[key] = whisperx.load_align_model(language_code=language, device=device()[0])
    return _models[key]


def align(text, audio, t0, language="en"):
    """wav2vec2 times for `text` inside `audio` (16 kHz float array starting at second t0).
    Returns every word: [(word, start, end)], with start/end None for words it couldn't place."""
    import whisperx
    am, meta = aligner(language)
    r = whisperx.align([{"start": 0.0, "end": len(audio) / 16000, "text": text}], am, meta, audio, device()[0],
                       return_char_alignments=False)
    return [(w["word"], t0 + w["start"] if "start" in w else None, t0 + w["end"] if "end" in w else None)
            for s in r["segments"] for w in s["words"]]


def transcribe(audio, language="en", prompt=None, words=True, vad=False, beam=5):
    """faster-whisper on a 16 kHz float array → list of segments with words."""
    segs, _ = whisper().transcribe(audio, language=language, beam_size=beam, word_timestamps=words,
                                   condition_on_previous_text=False, initial_prompt=prompt, vad_filter=vad)
    return list(segs)
