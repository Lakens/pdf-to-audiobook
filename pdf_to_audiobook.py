"""
pdf_to_audiobook.py — Convert a PDF to an MP3 audiobook.

Extraction chain (auto): GLM-OCR (Ollama) -> marker -> PyPDF2
TTS: Edge TTS (free, no API key needed)

Usage:
    py -3 pdf_to_audiobook.py path/to/book.pdf
    py -3 pdf_to_audiobook.py path/to/book.pdf --output path/to/output/folder
    py -3 pdf_to_audiobook.py path/to/book.pdf --extraction marker
    py -3 pdf_to_audiobook.py path/to/book.pdf --voice en-US-AriaNeural

Requirements:
    pip install edge-tts pymupdf ollama
    Ollama running with glm-ocr model: ollama pull glm-ocr

Optional (for marker extraction):
    pip install marker-pdf torch

Output folder contains:
    <title>.mp3          — audio file
    <title>_text.md      — extracted text (for inspection)
"""

import argparse
import asyncio
import base64
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_with_glm_ocr(pdf_path: Path) -> Optional[Tuple[str, str]]:
    """Extract text via GLM-OCR running locally in Ollama."""
    try:
        import ollama
        import fitz

        models = ollama.list()
        model_names = [m.model for m in models.models]
        if not any("glm-ocr" in m for m in model_names):
            print("WARNING: glm-ocr not found in Ollama. Run: ollama pull glm-ocr")
            return None

        print(f"  Extracting with GLM-OCR (Ollama) — {pdf_path.name}")
        doc = fitz.open(str(pdf_path))
        total = len(doc)
        page_texts = []

        for i, page in enumerate(doc):
            mat = fitz.Matrix(150 / 72, 150 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_b64 = base64.b64encode(pix.tobytes("jpeg")).decode("utf-8")
            response = ollama.generate(
                model="glm-ocr",
                prompt="Text Recognition: ",
                images=[img_b64],
                stream=False,
            )
            page_text = response["response"].strip()
            if page_text:
                page_texts.append(page_text)
            if (i + 1) % 10 == 0 or (i + 1) == total:
                print(f"  GLM-OCR: {i + 1}/{total} pages done")

        doc.close()
        text = "\n\n".join(page_texts)
        if text.strip():
            print(f"  OK: {len(text):,} characters extracted")
            return text, "GLM-OCR (Ollama)"
        return None
    except ImportError as e:
        print(f"WARNING: GLM-OCR missing dependency: {e}")
        return None
    except Exception as e:
        print(f"WARNING: GLM-OCR failed: {str(e)[:100]}")
        return None


def extract_with_marker(pdf_path: Path) -> Optional[Tuple[str, str]]:
    """Extract text via marker (local ML pipeline)."""
    try:
        import torch
        from marker.converters.pdf import PdfConverter
        from marker.models import create_model_dict
        from marker.output import text_from_rendered
        from marker.config.parser import ConfigParser

        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"  Extracting with marker (device={device}) — {pdf_path.name}")
        config = ConfigParser({"output_format": "markdown", "device": device, "disable_ocr": True})
        models = create_model_dict(device=device)
        converter = PdfConverter(config=config.generate_config_dict(), artifact_dict=models)
        rendered = converter(str(pdf_path))
        text, _, _ = text_from_rendered(rendered)
        if text and text.strip():
            print(f"  OK: {len(text):,} characters extracted")
            return text, "marker"
        return None
    except ImportError:
        print("WARNING: marker not installed. Run: pip install marker-pdf")
        return None
    except Exception as e:
        print(f"WARNING: marker failed: {str(e)[:100]}")
        return None


def extract_with_pypdf2(pdf_path: Path) -> Optional[Tuple[str, str]]:
    """Extract text via PyPDF2 (fallback)."""
    try:
        import PyPDF2
        print(f"  Extracting with PyPDF2 (fallback) — {pdf_path.name}")
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(pages)
        if text.strip():
            print(f"  OK: {len(text):,} characters extracted")
            return text, "PyPDF2"
        return None
    except ImportError:
        print("WARNING: PyPDF2 not installed. Run: pip install PyPDF2")
        return None
    except Exception as e:
        print(f"WARNING: PyPDF2 failed: {str(e)[:100]}")
        return None


def extract_text(pdf_path: Path, method: str = "auto") -> Tuple[str, str]:
    """Extract text using the specified method or auto chain."""
    if method == "glm-ocr":
        chain = [extract_with_glm_ocr]
    elif method == "marker":
        chain = [extract_with_marker]
    elif method == "pypdf":
        chain = [extract_with_pypdf2]
    else:
        # auto: GLM-OCR -> marker -> PyPDF2
        chain = [extract_with_glm_ocr, extract_with_marker, extract_with_pypdf2]

    for fn in chain:
        result = fn(pdf_path)
        if result:
            return result

    raise RuntimeError(f"Could not extract text from {pdf_path.name}")


# ---------------------------------------------------------------------------
# Text cleaning
# ---------------------------------------------------------------------------

def strip_markdown_headers(text: str) -> str:
    """Replace markdown header markers with plain text so TTS doesn't read '##'."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!\w)#{1,6}\s+(?=[A-Za-z0-9])', '', text)
    return text


def remove_non_speech_sections(text: str) -> str:
    """Drop references and non-prose blocks that hurt audiobook flow."""
    lines = text.splitlines()
    stop_headings = {
        "references",
        "bibliography",
        "works cited",
        "literature cited",
    }

    cutoff = len(lines)
    for idx, line in enumerate(lines):
        heading = re.sub(r'^\s*#{0,6}\s*', '', line).strip().lower()
        heading = re.sub(r'\s*[:\-]+\s*$', '', heading)
        if heading in stop_headings:
            cutoff = idx
            break

    filtered = []
    for line in lines[:cutoff]:
        s = line.strip()
        if not s:
            filtered.append("")
            continue

        if re.match(r'!\[[^\]]*\]\([^\)]+\)$', s):
            continue
        if re.match(r'^\|.*\|$', s):
            continue
        if re.match(r'^(?:https?://|doi\.org/|doi:\s*)', s, flags=re.IGNORECASE):
            continue
        if re.match(r'^(?:figure|fig\.?|table)\s*\d+[A-Za-z]?(?:\.\d+)?\s*[:\.\-)\s]', s, flags=re.IGNORECASE):
            continue

        filtered.append(line)

    return "\n".join(filtered)


def normalize_formula_text(text: str) -> str:
    """Convert common formula notation into speech-friendly plain text."""
    replacements = {
        "≤": " less than or equal to ",
        "≥": " greater than or equal to ",
        "≠": " not equal to ",
        "≈": " approximately ",
        "±": " plus or minus ",
        "α": " alpha ",
        "β": " beta ",
        "γ": " gamma ",
        "δ": " delta ",
        "μ": " mu ",
        "σ": " sigma ",
        "λ": " lambda ",
        "θ": " theta ",
        "π": " pi ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Common p-value notation
    text = re.sub(r'\bp\s*(?:<=|=<)\s*\.?([0-9]+)\b', r'p less than or equal to 0.\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp\s*(?:>=|=>)\s*\.?([0-9]+)\b', r'p greater than or equal to 0.\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp\s*<\s*\.?([0-9]+)\b', r'p less than 0.\1', text, flags=re.IGNORECASE)
    text = re.sub(r'\bp\s*>\s*\.?([0-9]+)\b', r'p greater than 0.\1', text, flags=re.IGNORECASE)

    def _latex_to_speech(expr: str) -> str:
        expr = re.sub(r'\\frac\s*\{([^{}]+)\}\s*\{([^{}]+)\}', r' \1 over \2 ', expr)
        expr = re.sub(r'\\(alpha|beta|gamma|delta|mu|sigma|lambda|theta|pi)\b', r' \1 ', expr)
        expr = re.sub(r'\\(leq|le)\b', ' less than or equal to ', expr)
        expr = re.sub(r'\\(geq|ge)\b', ' greater than or equal to ', expr)
        expr = re.sub(r'\\neq\b', ' not equal to ', expr)
        expr = re.sub(r'\\approx\b', ' approximately ', expr)
        expr = re.sub(r'\\pm\b', ' plus or minus ', expr)
        expr = re.sub(r'\\times\b', ' times ', expr)
        expr = re.sub(r'\\mid\b', ' given ', expr)
        expr = re.sub(r'[_^]\{?([^{}\s]+)\}?', r' \1 ', expr)
        expr = re.sub(r'\\[A-Za-z]+', ' ', expr)
        expr = re.sub(r'[{}]', ' ', expr)
        expr = re.sub(r'\s+', ' ', expr).strip()
        return expr

    text = re.sub(r'\$\$(.*?)\$\$', lambda m: f" {_latex_to_speech(m.group(1))} ", text, flags=re.DOTALL)
    text = re.sub(r'\$([^$\n]+?)\$', lambda m: f" {_latex_to_speech(m.group(1))} ", text)

    return text


def compress_in_text_citations(text: str) -> str:
    """Shorten in-line citation noise while preserving sentence flow."""
    def _paren_repl(match: re.Match) -> str:
        body = match.group(1)
        has_year = re.search(r'\b\d{4}[a-z]?\b', body) is not None
        looks_citation = has_year and (
            ';' in body
            or '&' in body
            or 'et al' in body.lower()
            or re.search(r'\b[A-Z][A-Za-z\-\'\.]+\s*,\s*\d{4}', body) is not None
        )
        if looks_citation:
            return ' (citation) '
        return match.group(0)

    text = re.sub(r'\(([^()]{3,220})\)', _paren_repl, text)
    text = re.sub(r'\[(?:\d{1,3}\s*(?:,|;)?\s*){1,8}\]', ' [citation] ', text)
    return text


def join_paragraphs_for_tts(text: str) -> str:
    """Join paragraph fragments with minimal punctuation for smoother speech."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    if not paragraphs:
        return ""

    merged = [paragraphs[0]]
    for para in paragraphs[1:]:
        prev = merged[-1]
        if re.search(r'[.!?]["\'\)\]]?\s*$', prev):
            merged.append(para)
        else:
            merged[-1] = prev.rstrip() + "."
            merged.append(para)

    return " ".join(merged)


def clean_text_for_tts(text: str) -> str:
    """Remove markdown and symbols that TTS reads aloud awkwardly."""
    # Remove hyphenated line-break artifacts early
    text = re.sub(r'-\s*\n\s*', '', text)
    # Remove markdown headers
    text = strip_markdown_headers(text)
    # Remove references and figure/table noise before joining paragraphs
    text = remove_non_speech_sections(text)
    # Join paragraphs with minimal pauses
    text = join_paragraphs_for_tts(text)
    # Convert formulas and symbols to speech-friendly text
    text = normalize_formula_text(text)
    # Remove markdown formatting
    text = re.sub(r'\*{1,3}', '', text)
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)
    text = re.sub(r'\^([^\s^]+)\^?', '', text)
    text = re.sub(r'`[^`]*`', '', text)
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)
    # Square brackets and curly braces
    text = re.sub(r'\[([^\]]+)\]', r'\1', text)
    text = re.sub(r'\{([^}]+)\}', r'\1', text)
    # Lone dollar signs
    text = re.sub(r'\$', '', text)
    # p. / pp. -> page / pages
    text = re.sub(r'\bpp\.\s*(\d)', r'pages \1', text)
    text = re.sub(r'\bp\.\s*(\d)', r'page \1', text)
    # ALL CAPS to title case
    text = re.sub(r'\b([A-Z]{2,})(?:\s+[A-Z]{2,})*\b', lambda m: m.group(0).title(), text)
    # Compress citations
    text = compress_in_text_citations(text)
    # Normalize repeated punctuation
    text = re.sub(r'(?:\s*\.\s*){3,}', '... ', text)
    text = re.sub(r'\.{4,}', '... ', text)
    # Remove lone special chars
    text = re.sub(r'(?<!\w)[~^|\\](?!\w)', ' ', text)
    # Collapse whitespace
    text = ' '.join(text.split())
    return text


# ---------------------------------------------------------------------------
# TTS synthesis
# ---------------------------------------------------------------------------

CHUNK_SIZE = 50_000


def chunk_text(text: str) -> list:
    """Split text into chunks at sentence boundaries."""
    if len(text) <= CHUNK_SIZE:
        return [text]
    chunks = []
    while text:
        if len(text) <= CHUNK_SIZE:
            chunks.append(text)
            break
        segment = text[:CHUNK_SIZE]
        best_idx = -1
        for sep in ('. ', '? ', '! ', '\n'):
            idx = segment.rfind(sep)
            if idx > CHUNK_SIZE // 2 and idx > best_idx:
                best_idx = idx
                best_sep = sep
        if best_idx == -1:
            best_idx = CHUNK_SIZE - 1
            best_sep = ' '
        split_at = best_idx + len(best_sep)
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()
    return chunks


def synthesize_tts(text: str, output_path: Path, voice: str = "en-US-AriaNeural") -> list:
    """Convert text to speech using Edge TTS streaming, capturing word timestamps.

    Returns a list of {word, start_sec} dicts — one per word boundary event.
    The timing sidecar is saved alongside the MP3 as <stem>_timing.json.
    """
    try:
        from edge_tts import Communicate
    except ImportError:
        raise RuntimeError("edge-tts not installed. Run: pip install edge-tts")

    import json
    import time as _time
    import tempfile

    chunks = chunk_text(text)
    print(f"  Voice: {voice}")
    print(f"  {len(text):,} chars, {len(chunks)} chunk(s)")

    all_boundaries = []
    time_offset = 0.0
    tmp_dir = Path(tempfile.mkdtemp())
    chunk_paths = []

    async def synth_chunk_async(chunk_text: str, chunk_path: Path):
        boundaries = []
        communicate = Communicate(text=chunk_text, voice=voice, rate="+20%")
        with open(chunk_path, "wb") as f:
            async for item in communicate.stream():
                if item["type"] == "audio":
                    f.write(item["data"])
                elif item["type"] in ("WordBoundary", "SentenceBoundary"):
                    boundaries.append({
                        "word":      item["text"],
                        "start_sec": item["offset"] / 10_000_000,
                    })
        return boundaries

    for i, chunk in enumerate(chunks):
        if len(chunks) > 1:
            print(f"  Chunk {i+1}/{len(chunks)} ({len(chunk):,} chars)...")
        chunk_path = tmp_dir / f"chunk_{i:04d}.mp3"

        for attempt in range(3):
            try:
                boundaries = asyncio.run(synth_chunk_async(chunk, chunk_path))
                break
            except Exception as exc:
                if attempt < 2 and "NoAudioReceived" in type(exc).__name__:
                    wait = (attempt + 1) * 5
                    print(f"  WARNING: No audio (attempt {attempt+1}/3), retrying in {wait}s...")
                    _time.sleep(wait)
                else:
                    raise

        for b in boundaries:
            all_boundaries.append({
                "word":      b["word"],
                "start_sec": round(b["start_sec"] + time_offset, 4),
            })

        chunk_paths.append(chunk_path)
        if boundaries:
            time_offset = all_boundaries[-1]["start_sec"] + 0.5
        if i < len(chunks) - 1:
            _time.sleep(2)

    # Concatenate chunks
    with open(output_path, "wb") as out:
        for cp in chunk_paths:
            out.write(cp.read_bytes())
            cp.unlink()
    tmp_dir.rmdir()

    print(f"  OK: {output_path.name} ({output_path.stat().st_size / 1e6:.1f} MB)")

    # Save timing sidecar
    timing_path = output_path.with_name(output_path.stem + "_timing.json")
    timing_path.write_text(json.dumps(all_boundaries, indent=2), encoding="utf-8")
    print(f"  OK: {timing_path.name} ({len(all_boundaries):,} word timestamps)")

    return all_boundaries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert a PDF to an MP3 audiobook.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("pdf", help="Path to input PDF")
    parser.add_argument("--output", "-o", default=None,
                        help="Output folder (default: <pdf_name>/ next to the PDF)")
    parser.add_argument("--extraction", choices=["auto", "glm-ocr", "marker", "pypdf"],
                        default="auto",
                        help="Extraction method (default: auto = glm-ocr -> marker -> pypdf)")
    parser.add_argument("--voice", default="en-US-AriaNeural",
                        help="Edge TTS voice (default: en-US-AriaNeural)")
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.exists():
        print(f"ERROR: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)

    title = pdf_path.stem
    output_dir = Path(args.output).resolve() if args.output else pdf_path.parent / title
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n=== PDF to Audiobook ===")
    print(f"Input:  {pdf_path.name}")
    print(f"Output: {output_dir}")
    print(f"Voice:  {args.voice}")
    print()

    # Step 1: Extract text
    print("[1/3] Extracting text...")
    start = datetime.now()
    text, method = extract_text(pdf_path, args.extraction)
    elapsed = (datetime.now() - start).total_seconds()
    print(f"  Method: {method} ({elapsed:.0f}s)")

    # Save extracted text
    text_path = output_dir / f"{title}_text.md"
    text_path.write_text(
        f"---\nsource: {pdf_path.name}\nextraction: {method}\ndate: {datetime.now().isoformat()}\n---\n\n{text}",
        encoding="utf-8"
    )
    print(f"  Text saved: {text_path.name}")

    # Step 2: Clean text
    print("\n[2/3] Cleaning text for TTS...")
    clean = clean_text_for_tts(text)
    print(f"  {len(clean):,} characters ready")

    # Step 3: TTS
    print("\n[3/3] Converting to speech...")
    audio_path = output_dir / f"{title}.mp3"
    synthesize_tts(clean, audio_path, voice=args.voice)

    timing_path = audio_path.with_name(audio_path.stem + "_timing.json")
    print(f"\n=== Done ===")
    print(f"Audio:   {audio_path}")
    print(f"Timing:  {timing_path}")
    print(f"Text:    {text_path}")


if __name__ == "__main__":
    main()
