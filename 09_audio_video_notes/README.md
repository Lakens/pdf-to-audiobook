# PDF to Speech Converter - Setup Guide

## Versioning

- Script version source: `SCRIPT_VERSION` in `pdf_to_speech.py`
- CLI version check: `python pdf_to_speech.py --version`
- Version style: semantic versioning (`MAJOR.MINOR.PATCH`)

## Version Updates

### v0.1.0 (2026-05-04)

- Added explicit script versioning (`SCRIPT_VERSION`) and a `--version` CLI flag.
- Improved Edge TTS compatibility across `edge-tts` iterator variants.
- Improved GLM-OCR diagnostics so blank exceptions are reported as `<no error message>`.
- Added GLM per-tile retry handling for tiled fallback OCR.
- Added GLM per-page embedded-text fallback when OCR fails.
- Made archive/move step non-fatal so successful conversions do not crash batch processing.
- Updated status wording to avoid overclaiming causes (`failed` vs uncertainty about empty pages).

## Lessons Learned

- Treat post-processing as best-effort: conversion success and archiving are separate outcomes.
- OCR engines can fail silently; logs should normalize empty exception text so failures are debuggable.
- Fallback chains should degrade gracefully and keep the batch running.
- Empty-page detection without image inspection is not reliable enough for automatic skipping.
- Large-batch pipelines need non-fatal error handling at every stage to prevent losing completed work.

## Quick Start

### 1. Install Dependencies
```powershell
cd "09_audio_video_notes"
pip install -r requirements.txt
```

### 2. Run It
Just drop a PDF in `pdfs_to_convert/` and run:
```powershell
python pdf_to_speech.py
# or double-click: convert.bat
```

That's it! The script handles text extraction and audio generation automatically.

## Key Features

✅ **Edge TTS** (default) — Excellent voice quality, free and unlimited (unofficial Edge read-aloud API, no account needed)  
✅ **Coqui TTS** (option) — Free, runs locally, unlimited processing  
✅ **Automatic text extraction** — Tries public Grobid servers → PyPDF2  
✅ **Rich metadata** — Word count, extraction date, TTS method auto-included  
✅ **Auto-archive** — Processed PDFs moved to `_processed/` folder  
✅ **Zero setup** — Just install requirements and drop a PDF  

## Text Extraction From GROBID

GROBID returns **TEI-formatted XML** (scholarly publishing standard), which contains:
- `<abstract>` — Document abstract
- `<body>` with `<div>` and `<p>` — Main organized sections and paragraphs  
- `<back>` — References (skipped)
- `<front>` — Metadata (skipped)

**Current extraction strategy:**
1. Extract abstract (if present) as markdown section
2. Extract body sections with hierarchical structure (preserves headers/subsections)
3. Skip metadata, references, and headers
4. Clean up and join paragraphs

**Output files:**
- `pdf_extracted_text/[filename]_extracted.md` — Raw extracted text with metadata
- `pdf_notes/[filename].md` — Full Obsidian note with audio link + extracted text
- `pdf_audio_outputs/[filename].mp3` — Generated audio file

## Output Format

Each converted PDF generates:

### Audio File (MP3)
- Name: `[pdf_name].mp3`
- Location: `pdf_audio_outputs/`
- Can be embedded in any Obsidian note via `[🎧 Listen](pdf_audio_outputs/file.mp3)`

### Extracted Text (Markdown)
- Name: `[pdf_name]_extracted.md`
- Location: `pdf_extracted_text/`
- Contains: YAML metadata + raw extracted text with preserved structure (headers, sections)
- Useful for: reviewing what was extracted, manual editing, or reference

### Obsidian Note (Markdown)
- Location: `pdf_notes/[pdf_name].md`
- Contains:
  - YAML frontmatter (extraction method, TTS method, stats)
  - Quick link to audio file
  - Summary (first 300 characters)
  - Full extracted text (cleaned)
  - Stats (word count, character count)

You can link between notes: `[[pdf_notes/Paper Title]]`

## Audio Note App + Local Transcription

This vault also supports a separate Android app for quick voice notes.

### What the audio note app does

- Single hold-to-record button
- Press and hold: starts recording
- Release: stops and saves
- File naming format: `audio_note_YYYYMMDDHHMMSS.m4a`
- Top mode switch:
  - Left: `audio_note` (default) -> save to `/storage/emulated/0/obsidian/09_audio_video_notes/audio_notes`
  - Right: `AI_task` -> save to `/storage/emulated/0/obsidian/09_audio_video_notes/AI_task`

Important Android permissions:

- `RECORD_AUDIO`
- Storage access (including all-files access on Android 11+)

### Local conversion (audio -> markdown transcript)

Use the local watcher script from your app repo:

`C:\Users\dlakens\OneDrive - TU Eindhoven\code_projects\audiobook_notetaker\scripts\transcribe_audio_notes.ps1`

Behavior on each run:

1. Checks whether Ollama is running.
2. Starts `ollama serve` if needed, then waits for ready state.
3. Scans these folders for `audio_note_*` files:
  `C:\Users\dlakens\OneDrive - TU Eindhoven\obsidian\09_audio_video_notes\audio_notes`
  `C:\Users\dlakens\OneDrive - TU Eindhoven\obsidian\09_audio_video_notes\AI_task`
4. Transcribes files using local Whisper model in Ollama.
5. Saves transcript as `.md` in the same folder as each source audio file.

Run manually:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\dlakens\OneDrive - TU Eindhoven\code_projects\audiobook_notetaker\scripts\transcribe_audio_notes.ps1"
```

Re-transcribe all files:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\dlakens\OneDrive - TU Eindhoven\code_projects\audiobook_notetaker\scripts\transcribe_audio_notes.ps1" -ReprocessAll
```

### Scheduled task (recommended)

Import this task XML in Windows Task Scheduler:

`C:\Users\dlakens\OneDrive - TU Eindhoven\code_projects\audiobook_notetaker\scripts\task_scheduler\transcribe_audio_notes_task.xml`

Task Scheduler import steps:

1. Open Task Scheduler.
2. Select Task Scheduler Library.
3. Click Import Task...
4. Select the XML file above.
5. Save the task.

The imported task is configured to run every 5 minutes, skip overlapping runs,
and write logs to:

`C:\Users\dlakens\OneDrive - TU Eindhoven\obsidian\09_audio_video_notes\audio_notes\transcribe_audio_notes.log`

## GROBID XML Extraction

GROBID returns TEI-formatted XML (academic publishing standard with `<abstract>`, `<body>`, `<back>`).

The script intelligently extracts from:
- **Abstract** — Markdown `##` section
- **Body** — Preserves section structure with hierarchical headers
- **Skipped** — metadata (`<front>`), references (`<back>`), boilerplate

Fallback to PyPDF2 if Grobid unavailable.

## Troubleshooting

### "edge-tts not found"
```powershell
pip install edge-tts
```

### "Could not extract text from PDF"
- Ensure PDF is not a scanned image (would need OCR)
- The script tries public Grobid servers → PyPDF2 automatically
- Check internet connection (for public Grobid servers)
- Try: `python pdf_to_speech.py --grobid skip` (PyPDF2 only)

### Grobid servers timing out / unavailable
- Public servers are free and may be slow/unreliable at peak times
- For reliable batch processing, set up local Docker instance:
  ```bash
  docker run -d -p 8070:8070 lfoppiano/grobid:latest
  python pdf_to_speech.py --grobid local
  ```
- Or skip Grobid and use PyPDF2: `python pdf_to_speech.py --grobid skip`

### FFmpeg errors
Install FFmpeg:
- **Windows**: `choco install ffmpeg` or get from https://ffmpeg.org/download.html
- **MacOS**: `brew install ffmpeg`
- **Linux**: `sudo apt install ffmpeg`

## Advanced Usage

### Single File Processing
```powershell
python pdf_to_speech.py --pdf "C:\path\to\paper.pdf"
```

### Use Custom Grobid Server
```powershell
python pdf_to_speech.py --grobid "http://your-server:port"
```

#### Use Local Grobid Only
```powershell
python pdf_to_speech.py --grobid local
```

#### Skip Grobid (Local Extraction Only - PyPDF2)
```powershell
python pdf_to_speech.py --grobid skip
```

### Vision-Based OCR: GLM-OCR Extraction

For **scanned PDFs or image-based content**, use the Ollama-hosted GLM-OCR model:

```powershell
# Requires: Ollama running with glm-ocr:latest model
# GPU: RTX A1000 6GB or similar (CUDA-enabled)
python pdf_to_speech.py --extraction glm-ocr
```

**Advantages:**
- Handles scanned documents that text extraction cannot (images as first-class content)
- Robust fallback system for memory-constrained GPUs
- Per-page OCR with automatic recovery

**Performance:**
- ~26-40 seconds per page depending on page complexity (RTX A1000 6GB)
- Adaptive memory management with intelligent fallback strategies
- Tested on 28 + 24 page PDFs with 100% completion rate

**Setup:**
```powershell
# Install Ollama from https://ollama.ai
ollama pull glm-ocr:latest
ollama serve  # Start the Ollama server in a separate terminal
# Then run the converter in another terminal
```

### Handling GPU Memory Crashes (Ollama Worker Crash Pattern)

**What happens:**
When extracting dense/complex PDF pages on GPUs with limited VRAM (~6GB), the OCR worker may crash with:
- Timeout after 60+ seconds on full-page 1024×1024px rendering
- Ollama worker process dies silently
- Subsequent attempts fail with "connection refused"

**Root cause:**
Full-page image normalization + vision model inference on memory-constrained GPU exceeds available VRAM, causing allocation failures.

**How we fixed it (automatic in current code):**

1. **Adaptive image downscaling** — If a page times out at full resolution:
   - Attempt 1: 1024 px (full quality)
   - Attempt 2: 896 px (reduced memory pressure)
   - Attempt 3: 768 px (further reduction)

2. **Tiled fallback** — If downscaling also times out, automatically decompose the page into 4 tiles:
   - Upper-left, upper-right, lower-left, lower-right quadrants
   - OCR each tile independently at normalized resolution
   - Reassemble results into single page text
   - Requires worker restart before tiling (handled automatically)

**Result:**
In testing, this recovered **7 out of 7 previously-failing pages** on a multi-page PDF batch without manual intervention. 100% completion rate achieved on 28 and 24-page PDFs despite initial worker crashes.

**You don't need to do anything** — the converter handles all recovery automatically. If you see messages like:
```
GLM-OCR page 7: trying tiled fallback (GLM-only) after page failure: Timeout
```

This is normal and expected. The page will complete via tiling.

### Marker Fast Mode

For faster Marker extraction without HTML/layout preservation:
```powershell
python pdf_to_speech.py --extraction marker --marker-mode fast
```

Fast mode trades strict layout accuracy for speed by:
- Disabling bounding box metadata (`ocr_without_boxes`)
- Skipping math-region detection (`disable_ocr_math`)
- Using larger batch sizes (recognition: 96, layout: 12, detection: 8)

**Note:** Marker startup may hang on Windows if Ollama is using GPU memory. Stop Ollama first:
```powershell
Stop-Process -Name ollama -Force -ErrorAction SilentlyContinue
```

## File Structure

```
09_audio_video_notes/
├── pdf_to_speech.py           # Main converter script
├── convert.bat                 # Windows launcher
├── requirements.txt            # Python dependencies
├── README.md                   # This file
├── pdfs_to_convert/            # ← Place PDFs here
│   └── _processed/             # Auto-archived after conversion
├── pdf_audio_outputs/          # Generated MP3 audio files
├── pdf_notes/                  # Generated Obsidian notes (with audio links + full text)
└── pdf_extracted_text/         # Raw extracted text with metadata (for reference/editing)
```

## Performance Tips

1. **Batch processing**: Place multiple PDFs and run once
2. **Long PDFs**: Large texts are automatically split into 50K-char chunks and concatenated
3. **First Coqui run**: Takes ~5-10 minutes to download & initialize model
4. **Edge TTS**: Processes ~100K characters per minute
5. **Parallel processing**: Run multiple instances for different PDFs

## Pricing

### Edge TTS
- **Free, no account needed** — uses the same API as Edge browser's read-aloud feature
- No documented character limit; not the paid Azure Cognitive Services

### Coqui TTS
- **Free**: No limits, runs locally

## API Keys (Future Extensions)

If you integrate paid services, create `.env`:
```
EDGE_TTS_API_KEY=your_key_here
OPENAI_API_KEY=for_future_llm_features
GROQ_API_KEY=for_llm_text_cleanup
```

Load in Python:
```python
from dotenv import load_dotenv
import os
load_dotenv()
api_key = os.getenv('EDGE_TTS_API_KEY')
```

---

## Change Log

### 2026-04-28

#### Improved TTS cleanup in `pdf_to_speech.py`

- Added references cutoff for spoken text generation.
  - The TTS cleanup now stops at common back-matter headings:
    - `References`
    - `Bibliography`
    - `Works Cited`
    - `Literature Cited`
  - This prevents long bibliography sections and DOI-only tails from being read out loud.

- Added non-prose filtering to reduce audiobook noise.
  - Drops markdown image-only lines (e.g., `![](...)`).
  - Drops markdown table rows used for contents/lists.
  - Drops standalone DOI/URL lines.
  - Drops common figure/table caption lines such as:
    - `Figure 1: ...`
    - `Fig. 3.2 ...`
    - `Table 4 ...`

- Added formula and symbol normalization for speech.
  - Converts common unicode symbols to words (examples: `≤`, `≥`, `≠`, `≈`, `±`).
  - Converts common Greek symbols to spoken names (examples: `α`, `β`, `μ`, `σ`, `λ`).
  - Converts common p-value notation to speech-friendly text:
    - `p < .05` -> `p less than 0.05`
    - `p <= .05` -> `p less than or equal to 0.05`
  - Converts many inline/block LaTeX fragments into plain spoken text instead of dropping them entirely.

- Added in-text citation compression.
  - Parenthetical author-year chains are compressed to `(citation)` when detected.
  - Numeric bracket citation lists are compressed to `[citation]`.
  - This improves listening flow while preserving a marker that a source was cited.

- Cleanup pipeline order updated for better results.
  - Header marker stripping now runs before section filtering.
  - Section filtering runs before paragraph joining.
  - Formula normalization runs before final punctuation and whitespace collapse.

- Scope and compatibility notes.
  - These changes affect TTS input preparation only.
  - Existing extracted markdown output format and note template structure are unchanged.

---

**Questions?** Check the main converter script comments or run `python pdf_to_speech.py --help`
