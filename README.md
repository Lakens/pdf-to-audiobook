# PDF to Audiobook

Convert any PDF (academic book, paper, report) to an MP3 audiobook using local AI for text extraction and free cloud TTS for audio synthesis.

## How it works

```
PDF → [GLM-OCR / marker / PyPDF2] → cleaned text → [Edge TTS] → MP3
```

### Step 1 — Text extraction

Three methods are tried in order (auto mode):

1. **GLM-OCR** (default) — A 0.9B vision model running locally via [Ollama](https://ollama.com). Renders each PDF page as an image and reads it with AI. Handles complex layouts, footnotes, and figures. Uses your GPU if available.
2. **marker** — A heavier ML pipeline (layout detection + optional OCR). Also GPU-accelerated. Falls back to this if GLM-OCR is unavailable.
3. **PyPDF2** — Simple text extraction. Fast but loses structure; last resort.

### Step 2 — Text cleaning

Before synthesis, the extracted text is cleaned:
- Markdown headers (`##`, `###`) are stripped
- Symbols TTS reads awkwardly are removed: `^`, `~`, `|`, `\`
- Subscript/superscript notation (`H_2_O`, `^13^C`) is cleaned up
- Markdown links, bold/italic markers, inline code are removed

### Step 3 — Text-to-speech

Uses [Edge TTS](https://github.com/rany2/edge-tts) — Microsoft's neural TTS, free and requires no API key. Long texts are automatically split into chunks and joined into a single MP3.

---

## Requirements

### Core (required)
```
pip install edge-tts pymupdf
```

### GLM-OCR (recommended — best quality)
1. Install [Ollama](https://ollama.com/download)
2. Pull the model:
   ```
   ollama pull glm-ocr
   ```
3. Install the Python client:
   ```
   pip install ollama
   ```
   Ollama must be running before you start (`ollama serve` or the desktop app).

### marker (optional — alternative to GLM-OCR)
```
pip install marker-pdf torch
```
GPU (CUDA) is strongly recommended; CPU extraction is very slow for long books.

### ffmpeg (optional — for cleaner MP3 joining)
Download from [ffmpeg.org](https://ffmpeg.org/download.html) and add to PATH.
Without ffmpeg, chunks are joined via raw binary concatenation (usually fine).

---

## Usage

### Standalone script

```bash
# Basic — uses auto extraction (GLM-OCR preferred)
py -3 pdf_to_audiobook.py "path/to/my_paper.pdf"

# Specify output folder
py -3 pdf_to_audiobook.py my_paper.pdf --output C:/Audiobooks/my_paper

# Force a specific extraction method
py -3 pdf_to_audiobook.py my_paper.pdf --extraction marker
py -3 pdf_to_audiobook.py my_paper.pdf --extraction glm-ocr
py -3 pdf_to_audiobook.py my_paper.pdf --extraction pypdf

# Change TTS voice
py -3 pdf_to_audiobook.py my_paper.pdf --voice en-GB-SoniaNeural
```

Output is placed in a folder named after the PDF (next to it), or in `--output`:
```
my_paper/
  my_paper.mp3         ← audiobook
  my_paper_timing.json ← word-level timestamps
  my_paper_text.md     ← extracted text (for inspection)
```

The timing file maps every word to its position in the audio:
```json
[
  {"word": "Introduction", "start_sec": 0.0},
  {"word": "This", "start_sec": 0.612},
  {"word": "paper", "start_sec": 0.875},
  ...
]
```
This enables building a read-along player, chapter navigation, or searching for a passage and jumping directly to that point in the audio.

### Obsidian integration

The Obsidian version (`pdf_to_speech.py`) integrates with your vault:
- Reads the selected PDF from a side-channel file (`pdf_to_convert_pending.txt`)
- Creates an Obsidian note with an embedded audio player, progress tracker, and timestamp button
- Archives the PDF after processing
- Triggered via a DataviewJS button in your home note

Both scripts share the same extraction chain and cleaning logic.

---

## Available voices

Some good Edge TTS voices:

| Voice | Description |
|---|---|
| `en-US-AriaNeural` | US English, female (default) |
| `en-US-GuyNeural` | US English, male |
| `en-GB-SoniaNeural` | British English, female |
| `en-GB-RyanNeural` | British English, male |
| `en-AU-NatashaNeural` | Australian English, female |

List all available voices:
```bash
py -3 -m edge_tts --list-voices
```

---

## Performance notes

- **GLM-OCR on GPU**: ~5–10 pages/minute (RTX A1000 6GB). A 334-page book takes ~50 min.
- **GLM-OCR on CPU**: much slower, not recommended for books.
- **marker on GPU** (OCR disabled): ~3 pages/sec for layout, then fast text extraction.
- **TTS**: ~1–2 minutes per 50,000 characters via Edge TTS.

For a full academic book (~330 pages), expect 1–2 hours total.

---

## Tips

- If Ollama is not running, GLM-OCR will fail and the script falls back to marker, then PyPDF2.
- The extracted text is always saved separately so you can inspect quality before committing to TTS.
- For very large books, Edge TTS occasionally drops a chunk (`NoAudioReceived`). Re-running the script will redo only the failed run.

---

## Change Log

### 2026-04-28 — Improved TTS cleanup pipeline

Enhanced `clean_text_for_tts()` with four new text filtering features to improve audiobook quality:

1. **References cutoff** — Detects common reference section headings (References, Bibliography, Works Cited, Literature Cited) and discards all text from that point onward. Prevents reading of citation lists that add no value to speech output.

2. **Non-prose filtering** — Removes tables, figures, image captions, and DOI-only lines before TTS. Academic papers often contain dense tables and figure captions that don't narrate well; filtering these improves listening flow.

3. **Formula normalization** — Converts mathematical notation to speech-friendly text:
   - Unicode symbols: `≤` → "less than or equal to", `α` → "alpha", `π` → "pi"
   - p-value notation: `p < .05` → "p less than 0.05"
   - LaTeX fragments: `\frac{a}{b}` → "a over b"

4. **Citation compression** — Shortens in-text citations and reference lists:
   - Parenthetical citations: `(Smith & Jones, 2020; cf. Brown et al., 2019)` → `(citation)`
   - Bracketed citations: `[1, 2, 3]` → `[citation]`
   Preserves structural markers while reducing auditory noise.

**Pipeline improvements:**
- Markdown header stripping moved before paragraph joining to prevent headers from becoming inline noise
- Intelligent paragraph joining replaces blanket period insertion; preserves existing punctuation boundaries
- Formula normalization converts symbols to speech rather than silent removal for mathematical papers

**Scope:** All four improvements are generic text filters and apply identically to both standalone and Obsidian versions.
