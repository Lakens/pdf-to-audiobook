#!/usr/bin/env python3
"""
PDF to Speech Converter for Obsidian
Extracts text from PDFs and converts to audio files.
Generates notes in the same style as YouTube/podcast notes, with audio player,
timestamp button, and transcribe button.

Usage:
    py -3 pdf_to_speech.py --vault "C:\\path\\to\\vault" --note "C:\\...\\01 - Home_Audio_Video.md"
    py -3 pdf_to_speech.py --vault "..." --note "..." --pdf "filename.pdf"
    py -3 pdf_to_speech.py --vault "..." --note "..." --tts coqui

The script reads the selected PDF filename from
  <vault>/99 - System/pdf_to_convert_pending.txt
unless --pdf is passed directly.
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import subprocess

SCRIPT_VERSION = "0.1.0"

# Try to import optional dependencies
try:
    import requests
except ImportError:
    requests = None



# ---------------------------------------------------------------------------
# DataviewJS blocks — identical to those in download_youtube.py
# ---------------------------------------------------------------------------

AUDIO_PLAYER = r"""```dataviewjs
(async () => {
    const fm = dv.current();
    const audioFile = fm.audio_file;
    const mediaFolder = fm.media_folder;
    if (!audioFile || !mediaFolder) {
        dv.el("p", "No audio_file / media_folder in frontmatter.");
        return;
    }
    const obsFile = app.vault.getAbstractFileByPath(mediaFolder + "/" + audioFile);
    if (!obsFile) {
        dv.el("p", "Audio file not found in vault: " + audioFile);
        return;
    }
    const src = app.vault.getResourcePath(obsFile);
    const C = this.container;

    const style = C.createEl("style");
    style.textContent = `
        .cp { font-family: sans-serif; max-width: 520px; padding: 10px 0; user-select: none; }
        .cp-top { display:flex; align-items:center; justify-content:center; gap:24px; margin-bottom:10px; }
        .cp-play { font-size:2.8em; width:1.4em; height:1.4em; background:none; border:none;
                   cursor:pointer; line-height:1; display:flex; align-items:center; justify-content:center; }
        .cp-skip { font-size:0.9em; background:none; border:none; cursor:pointer;
                   display:flex; flex-direction:column; align-items:center; gap:1px;
                   color: var(--text-normal); }
        .cp-skip .cp-skip-icon { font-size:2.5em; line-height:1; }
        .cp-skip .cp-skip-lbl { font-size:0.7em; opacity:0.7; }
        .cp-timeline { display:flex; align-items:center; gap:8px; margin-bottom:10px;
                       font-size:0.82em; color:var(--text-muted); }
        .cp-seek { flex:1; height:4px; cursor:pointer; accent-color:var(--interactive-accent); }
        .cp-extras { display:flex; align-items:center; gap:8px; flex-wrap:wrap; font-size:0.82em; }
        .cp-spd { background:none; border:1px solid var(--background-modifier-border);
                  border-radius:4px; padding:2px 7px; cursor:pointer; font-size:0.82em;
                  color:var(--text-normal); }
        .cp-spd.on { background:var(--interactive-accent); color:#fff;
                     border-color:var(--interactive-accent); }
        .cp-vol { width:70px; accent-color:var(--interactive-accent); }
    `;

    const wrap = C.createEl("div", { cls: "cp" });
    const audio = wrap.createEl("audio");
    audio.src = src;
    audio.style.display = "none";

    // — top row —
    const top = wrap.createEl("div", { cls: "cp-top" });

    const rwBtn = top.createEl("button", { cls: "cp-skip", title: "Rewind 30 s" });
    rwBtn.createEl("span", { cls: "cp-skip-icon", text: "⏪" });
    rwBtn.createEl("span", { cls: "cp-skip-lbl",  text: "30 s" });

    const playBtn = top.createEl("button", { cls: "cp-play", text: "▶" });

    const fwBtn = top.createEl("button", { cls: "cp-skip", title: "Forward 30 s" });
    fwBtn.createEl("span", { cls: "cp-skip-icon", text: "⏩" });
    fwBtn.createEl("span", { cls: "cp-skip-lbl",  text: "30 s" });

    // — timeline —
    const tl = wrap.createEl("div", { cls: "cp-timeline" });
    const cur = tl.createEl("span", { text: "0:00" });
    const seek = tl.createEl("input", { attr: { type:"range", min:0, max:100, value:0, step:0.05 } });
    seek.classList.add("cp-seek");
    const dur = tl.createEl("span", { text: "0:00" });

    // — extras —
    const ext = wrap.createEl("div", { cls: "cp-extras" });
    const speeds = [0.5, 0.75, 1, 1.25, 1.5, 2];
    const spdBtns = speeds.map(sp => {
        const b = ext.createEl("button", { cls: "cp-spd" + (sp === 1 ? " on" : ""), text: sp + "x" });
        b.addEventListener("click", () => {
            audio.playbackRate = sp;
            spdBtns.forEach(x => x.classList.remove("on"));
            b.classList.add("on");
        });
        return b;
    });
    ext.createEl("span", { text: "🔊", attr: { style: "margin-left:8px;" } });
    const vol = ext.createEl("input", { attr: { type:"range", min:0, max:1, step:0.05, value:1 } });
    vol.classList.add("cp-vol");

    // — helpers —
    const fmt = s => {
        const h = Math.floor(s/3600), m = Math.floor((s%3600)/60), sc = Math.floor(s%60);
        return h > 0 ? `${h}:${String(m).padStart(2,"0")}:${String(sc).padStart(2,"0")}`
                     : `${m}:${String(sc).padStart(2,"0")}`;
    };

    // — events —
    playBtn.addEventListener("click", () => audio.paused ? audio.play() : audio.pause());
    audio.addEventListener("play",  () => { playBtn.textContent = "⏸"; });
    audio.addEventListener("pause", () => { playBtn.textContent = "▶"; });
    audio.addEventListener("ended", () => { playBtn.textContent = "▶"; });
    rwBtn.addEventListener("click", () => { audio.currentTime = Math.max(0, audio.currentTime - 30); });
    fwBtn.addEventListener("click", () => { audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 30); });
    audio.addEventListener("timeupdate", () => {
        cur.textContent = fmt(audio.currentTime);
        if (audio.duration) seek.value = (audio.currentTime / audio.duration) * 100;
    });
    audio.addEventListener("loadedmetadata", async () => {
        dur.textContent = fmt(audio.duration);

        // Restore saved playback position
        try {
            const raw = await app.vault.adapter.read("99 - System/playback_positions.json");
            const positions = JSON.parse(raw);
            const saved = positions[app.workspace.getActiveFile()?.path];
            if (saved && saved > 2 && saved < audio.duration - 30) {
                audio.currentTime = saved;
            }
        } catch(e) {}
    });
    audio.addEventListener("pause", async () => {
        if (audio.currentTime < 2) return;
        try {
            const activeFile = app.workspace.getActiveFile();
            if (!activeFile) return;
            let positions = {};
            try {
                const raw = await app.vault.adapter.read("99 - System/playback_positions.json");
                positions = JSON.parse(raw);
            } catch(e) {}
            positions[activeFile.path] = Math.floor(audio.currentTime);
            await app.vault.adapter.write("99 - System/playback_positions.json", JSON.stringify(positions, null, 2));
        } catch(e) {}
    });
    seek.addEventListener("input", () => {
        if (audio.duration) audio.currentTime = (parseFloat(seek.value) / 100) * audio.duration;
    });
    vol.addEventListener("input", () => { audio.volume = parseFloat(vol.value); });

    // Save position every 5 s while playing — guards against navigation without pause
    const savePosition = async () => {
        if (audio.paused || audio.currentTime < 2) return;
        try {
            const activeFile = app.workspace.getActiveFile();
            if (!activeFile) return;
            let positions = {};
            try {
                const raw = await app.vault.adapter.read("99 - System/playback_positions.json");
                positions = JSON.parse(raw);
            } catch(e) {}
            positions[activeFile.path] = Math.floor(audio.currentTime);
            await app.vault.adapter.write("99 - System/playback_positions.json", JSON.stringify(positions, null, 2));
        } catch(e) {}
    };
    const _interval = setInterval(savePosition, 5000);
    // Clean up interval when the player is removed from the DOM
    new MutationObserver(() => {
        if (!wrap.isConnected) clearInterval(_interval);
    }).observe(wrap.parentElement || C, { childList: true, subtree: true });
})();
```"""


TIMESTAMP_BUTTON = r"""```dataviewjs
(async () => {
    const LOG = "99 - System/timestamp_log.json";
    const file = app.workspace.getActiveFile();
    if (!file) return;

    if (window._cpWriting) return;

    const C = this.container;
    const btn = C.createEl("button", {
        text: "⏱ Mark timestamp",
        attr: { style: "padding:5px 16px; cursor:pointer; font-size:0.95em;" }
    });
    const status = C.createEl("span", {
        attr: { style: "font-size:0.82em; color:var(--text-muted); margin-left:10px;" }
    });

    const fmt = t => {
        const h = Math.floor(t/3600), m = Math.floor((t%3600)/60), s = Math.floor(t%60);
        return h > 0 ? `${h}:${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`
                     : `${String(m).padStart(2,"0")}:${String(s).padStart(2,"0")}`;
    };

    btn.addEventListener("click", async () => {
        if (window._cpWriting) return;
        const all = [...document.querySelectorAll("audio,video")];
        const media = all.find(m => !m.paused) ?? all.find(m => m.currentTime > 0) ?? all[0];
        if (!media) { new Notice("No audio or video found in this note."); return; }
        const t = media.currentTime;
        if (t === 0) { new Notice("Audio is at 0:00 — play or seek first."); return; }

        const ts = fmt(t);
        window._cpWriting = true;
        try {
            let entries = [];
            try {
                const raw = await app.vault.adapter.read(LOG);
                entries = JSON.parse(raw);
            } catch(e) { entries = []; }

            entries.push({
                note_path: file.path,
                note_title: app.metadataCache.getFileCache(file)?.frontmatter?.title || file.basename,
                timestamp: ts,
                seconds: Math.floor(t),
                logged_at: new Date().toISOString(),
                processed: false
            });

            await app.vault.adapter.write(LOG, JSON.stringify(entries, null, 2));
            status.textContent = `✓ ${ts}`;
            setTimeout(() => { status.textContent = ""; }, 2500);
            new Notice(`⏱ Logged: ${ts}`);
        } catch(e) {
            new Notice("Error writing timestamp log: " + e.message);
        } finally {
            window._cpWriting = false;
        }
    });
})();
```"""


TRANSCRIBE_BUTTON = r"""```dataviewjs
(async () => {
    const PENDING = "99 - System/transcribe_pending.txt";
    const MONITOR = "99 - System/transcribe_monitor";
    const file = app.workspace.getActiveFile();
    if (!file) return;
    const C = this.container;
    const btn = C.createEl("button", {
        text: "🎙 Transcribe with Whisper",
        attr: { style: "padding:5px 16px; cursor:pointer; font-size:0.95em;" }
    });
    btn.addEventListener("click", async () => {
        btn.disabled = true;
        btn.textContent = "⏳ Starting…";
        await app.vault.adapter.write(PENDING, file.path);
        window.open("obsidian://shell-commands?vault=obsidian&execute=transcribe-audio");
        setTimeout(() => {
            app.workspace.openLinkText(MONITOR, "", true);
        }, 800);
        setTimeout(() => { btn.disabled = false; btn.textContent = "🎙 Transcribe with Whisper"; }, 4000);
    });
})();
```"""


# ---------------------------------------------------------------------------
# Progress reporter — writes directly to a vault file so Obsidian can read it
# ---------------------------------------------------------------------------

import re as _re

def _strip_code_fences(text: str) -> str:
    """Strip markdown code fences that GLM-OCR sometimes wraps around output."""
    blocks = _re.split(r"```[a-zA-Z]*\n?", text)
    if len(blocks) <= 1:
        return text.strip()
    inner = [b.strip() for b in blocks if b.strip()]
    joined = "\n\n".join(inner) if inner else text.strip()
    cleaned = [ln for ln in joined.splitlines()
               if not _re.match(r"^```[a-zA-Z]*$", ln.strip())]
    return "\n".join(cleaned).strip()

class Progress:
    """Writes live progress to pdf_convert_progress.md, polled by Obsidian DataviewJS."""

    STEPS = [
        ("🔍", "Extracting text from PDF"),
        ("✂️", "Preparing text for TTS"),
        ("🔊", "Converting text to speech"),
        ("📝", "Creating Obsidian note"),
    ]

    def __init__(self, vault: Path, pdf_name: str,
                 batch_index: int = 0, batch_total: int = 1,
                 completed_log: list = None):
        self.path = vault / "99 - System" / "pdf_convert_progress.md"
        self.pdf_name = pdf_name
        self.batch_index = batch_index
        self.batch_total = batch_total
        self.completed_log = completed_log or []
        self.current_step = 0
        self._substep_line = ""
        self._render()

    def step(self, n: int, detail: str = ""):
        self.current_step = n
        self._substep_line = ""
        self._render(detail)

    def substep(self, n: int, label: str, done: int, total: int):
        self._substep_line = (
            f"`{self._bar(done, total, 20)}`  {done}/{total}  ({label})"
        )
        self._render()

    def done(self, note_name: str, elapsed: float):
        self.current_step = len(self.STEPS)
        self._substep_line = ""
        self._render()

    def error(self, step_name: str, msg: str):
        lines = [self._batch_header(),
                 f"",
                 f"**FAILED** — {self.pdf_name}",
                 f"Step: {step_name}",
                 f"Error: {msg[:120]}"]
        self._write("\n".join(lines))

    # ------------------------------------------------------------------ #

    def _batch_header(self) -> str:
        done = len(self.completed_log)
        bar = self._bar(done, self.batch_total, 30)
        return f"### Batch: {done}/{self.batch_total} complete `{bar}`  {done}/{self.batch_total} PDFs"

    def _render(self, detail: str = ""):
        n = self.current_step
        lines = [
            self._batch_header(),
            f"",
            f"**Now:** {self.pdf_name}  *(PDF {self.batch_index+1}/{self.batch_total})*",
            f"",
        ]
        icons = ["⏳", "✅"]
        for i, (icon, label) in enumerate(self.STEPS):
            step_n = i + 1
            if step_n < n:
                lines.append(f"✅ {icon} {label}")
            elif step_n == n:
                d = f" — {detail}" if detail else ""
                lines.append(f"⏳ {icon} {label}{d}")
            else:
                lines.append(f"⬜ {icon} {label}")

        if n > 0:
            lines.append(f"")
            lines.append(f"`{self._bar(n-1, len(self.STEPS), 20)}`  Step {n}/{len(self.STEPS)}")

        if self._substep_line:
            lines.append(f"`{self._bar(0, 20, 20)}`  " if False else self._substep_line)

        self._write("\n".join(lines))

    def _bar(self, done: int, total: int, width: int = 20) -> str:
        if total == 0:
            return "░" * width
        filled = round(done / total * width)
        return "█" * filled + "░" * (width - filled)

    def _write(self, text: str):
        try:
            self.path.write_text(text + "\n", encoding="utf-8")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def strip_markdown_headers(text: str) -> str:
    """Replace markdown header markers with plain text so TTS doesn't read '##'."""
    # Remove heading markers at line starts and residual inline heading markers.
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    text = re.sub(r'(?<!\w)#{1,6}\s+(?=[A-Za-z0-9])', '', text)
    return text


def join_paragraphs_for_tts(text: str) -> str:
    """Join paragraph fragments with minimal punctuation for smoother speech."""
    paragraphs = [p.strip() for p in re.split(r'\n{2,}', text) if p.strip()]
    if not paragraphs:
        return ""

    merged = [paragraphs[0]]
    for para in paragraphs[1:]:
        prev = merged[-1]
        # Keep a soft join when prior chunk already ends as a sentence.
        if re.search(r'[.!?]["\'\)\]]?\s*$', prev):
            merged.append(para)
        else:
            merged[-1] = prev.rstrip() + "."
            merged.append(para)

    return " ".join(merged)


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


def clean_text_for_tts(text: str, max_chars: int = 5_000_000) -> str:
    """Strip markdown and scientific notation symbols unsuitable for TTS."""
    # Fix 6: Hyphenated line-break artifacts (e.g. "eigh-\nteenth") before any whitespace collapse
    text = re.sub(r'-\s*\n\s*', '', text)
    # Remove markdown heading markers early so section detection sees plain headings.
    text = strip_markdown_headers(text)
    # Remove references and figure/table-heavy lines before joining paragraphs.
    text = remove_non_speech_sections(text)
    # Join paragraph fragments with fewer forced pauses.
    text = join_paragraphs_for_tts(text)
    # Convert formulas and symbols to speech-friendly text.
    text = normalize_formula_text(text)
    # Remove markdown formatting symbols
    text = re.sub(r'\*{1,3}', '', text)          # bold/italic asterisks
    text = re.sub(r'_{1,2}([^_]+)_{1,2}', r'\1', text)  # _subscript_ or __text__
    text = re.sub(r'\^([^\s^]+)\^?', '', text)   # ^superscript^
    text = re.sub(r'`[^`]*`', '', text)           # inline code
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)  # [label](url) -> label
    text = re.sub(r'!\[[^\]]*\]\([^\)]+\)', '', text)      # ![image](url) -> removed
    # Fix 1: Square brackets (editorial insertions, e.g. [sic], [the]) -> keep inner text
    text = re.sub(r'\[([^\]]+)\]', r'\1', text)
    # Fix 3: Curly braces (LaTeX/OCR artifacts) -> keep inner text
    text = re.sub(r'\{([^}]+)\}', r'\1', text)
    # Lone dollar signs
    text = re.sub(r'\$', '', text)
    # Fix 2: p. / pp. -> page / pages
    text = re.sub(r'\bpp\.\s*(\d)', r'pages \1', text)
    text = re.sub(r'\bp\.\s*(\d)', r'page \1', text)
    # Fix 5: ALL CAPS words (headings) -> title case
    text = re.sub(r'\b([A-Z]{2,})(?:\s+[A-Z]{2,})*\b', lambda m: m.group(0).title(), text)
    # Compress citation parentheticals to reduce speech interruptions.
    text = compress_in_text_citations(text)
    # Normalize repeated punctuation artifacts that create unnatural pauses.
    text = re.sub(r'(?:\s*\.\s*){3,}', '... ', text)
    text = re.sub(r'\.{4,}', '... ', text)
    # Remove lone special characters that TTS reads aloud awkwardly
    text = re.sub(r'(?<!\w)[~^|\\](?!\w)', ' ', text)
    # Collapse whitespace
    text = ' '.join(text.split())
    if len(text) > max_chars:
        print(f"WARNING: Text truncated from {len(text)} to {max_chars} characters")
        text = text[:max_chars]
    return text


def chunk_text_for_tts(text: str, chunk_size: int = 50_000) -> list:
    """Split text into chunks at sentence boundaries for chunked TTS synthesis."""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    while text:
        if len(text) <= chunk_size:
            chunks.append(text)
            break
        segment = text[:chunk_size]
        # Find the last sentence boundary in the segment
        best_idx = -1
        for sep in ('. ', '? ', '! ', '\n'):
            idx = segment.rfind(sep)
            if idx > chunk_size // 2 and idx > best_idx:
                best_idx = idx
                best_sep = sep
        if best_idx == -1:
            # No good boundary found; break at chunk_size
            best_idx = chunk_size - 1
            best_sep = ' '
        split_at = best_idx + len(best_sep)
        chunks.append(text[:split_at].strip())
        text = text[split_at:].strip()

    return chunks


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

class PDFExtractor:
    """Extract text from PDF files."""

    PUBLIC_GROBID_SERVERS = [        "https://grobid.petal.org",
        "https://orkg.org/grobid",
        "http://localhost:8070",
    ]

    def __init__(self, grobid_server: str = None, extraction: str = "auto", marker_mode: str = "quality"):
        if grobid_server == "local":
            self.grobid_servers = ["http://localhost:8070"]
        elif grobid_server and grobid_server != "skip":
            self.grobid_servers = [grobid_server]
        else:
            self.grobid_servers = self.PUBLIC_GROBID_SERVERS
        # extraction: "auto" | "marker" | "grobid" | "pypdf"
        self.extraction = extraction
        self.marker_mode = marker_mode

    def extract_with_marker(self, pdf_path: str, progress=None) -> Optional[Tuple[str, str]]:
        """Extract text via marker (local ML pipeline). Returns (text, method)."""
        try:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict
            from marker.output import text_from_rendered
            from marker.config.parser import ConfigParser
            import tqdm as _tqdm_mod
            import sys as _sys

            print(f"      Running marker (local ML extraction)...")
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
            if device == "cuda":
                try:
                    gpu_name = torch.cuda.get_device_name(0)
                except Exception:
                    gpu_name = "unknown GPU"
                print(f"      Marker device: CUDA ({gpu_name})")
            else:
                print("      Marker device: CPU")

            orig_tqdm = _tqdm_mod.tqdm
            patched_marker_modules = []

            if progress is not None:
                class _ProgressTqdm(orig_tqdm):
                    def __init__(self, *args, **kwargs):
                        super().__init__(*args, **kwargs)
                        self._emit_progress()

                    def update(self, n=1):
                        out = super().update(n)
                        self._emit_progress()
                        return out

                    def refresh(self, *args, **kwargs):
                        out = super().refresh(*args, **kwargs)
                        self._emit_progress()
                        return out

                    def _emit_progress(self):
                        try:
                            total = int(self.total) if self.total else 0
                            done = int(self.n) if self.n is not None else 0
                            done = min(done, total) if total else done
                            if total > 0:
                                desc = (self.desc or "marker").strip().replace(":", "")
                                progress.substep(1, f"marker — {desc}", done, total)
                        except Exception:
                            pass

                _tqdm_mod.tqdm = _ProgressTqdm
                for _mod_name, _mod in list(_sys.modules.items()):
                    if not _mod_name:
                        continue
                    if not (_mod_name.startswith("marker.") or _mod_name.startswith("surya.")):
                        continue
                    if hasattr(_mod, "tqdm"):
                        try:
                            _existing_tqdm = getattr(_mod, "tqdm")
                            if callable(_existing_tqdm):
                                setattr(_mod, "tqdm", _ProgressTqdm)
                                patched_marker_modules.append((_mod, _existing_tqdm))
                        except Exception:
                            pass

            marker_cfg = {"output_format": "markdown", "device": device}
            if self.marker_mode == "fast":
                print("      Marker mode: FAST (ocr_without_boxes, no OCR math)")
                # Fast mode reduces OCR overhead. Quality mode remains the default.
                marker_cfg.update({
                    "ocr_task_name": "ocr_without_boxes",
                    "disable_ocr_math": True,
                    # Slightly larger batches help throughput on CUDA when VRAM allows it.
                    "recognition_batch_size": 96 if device == "cuda" else 32,
                    "layout_batch_size": 12 if device == "cuda" else 4,
                    "detection_batch_size": 8 if device == "cuda" else 4,
                })

            config = ConfigParser(marker_cfg)
            models = create_model_dict(device=device)
            converter = PdfConverter(config=config.generate_config_dict(), artifact_dict=models)
            try:
                rendered = converter(pdf_path)
            finally:
                _tqdm_mod.tqdm = orig_tqdm
                for _mod, _old_tqdm in patched_marker_modules:
                    try:
                        setattr(_mod, "tqdm", _old_tqdm)
                    except Exception:
                        pass
            text, _, _ = text_from_rendered(rendered)
            if text and text.strip():
                print(f"OK: Extracted with marker ({len(text):,} chars)")
                return text, "marker"
            print("WARNING: marker returned empty text")
            return None
        except ImportError:
            print("WARNING: marker not installed. Run: pip install marker-pdf")
            return None
        except Exception as e:
            print(f"WARNING: marker extraction failed: {str(e)[:80]}")
            return None

    def extract_with_glm_ocr(self, pdf_path: str, progress=None) -> Optional[Tuple[str, str]]:
        """Extract text via GLM-OCR via Ollama REST API (urllib, no Python client).

        Uses urllib per page to avoid the GGML_ASSERT crash that occurs when the
        Python ollama client reuses state across multimodal calls.
        """
        import base64
        import tempfile
        import shutil as _sh
        import time as _t
        import urllib.request as _ur
        import urllib.error as _ue
        import concurrent.futures as _cf
        import io as _io
        import json as _js

        if not ensure_ollama_running():
            print("WARNING: GLM-OCR skipped — Ollama could not be started")
            return None

        try:
            import fitz
        except ImportError:
            print("WARNING: GLM-OCR missing dependency: pymupdf  (pip install pymupdf)")
            return None

        try:
            with _ur.urlopen("http://localhost:11434/api/tags", timeout=5) as r:
                tags = _js.loads(r.read())
            if not any("glm-ocr" in m["name"] for m in tags.get("models", [])):
                print("WARNING: glm-ocr not found. Run: ollama pull glm-ocr")
                return None
        except Exception as e:
            print(f"WARNING: Cannot reach Ollama: {e}")
            return None

        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            print(f"WARNING: Cannot open PDF: {e}")
            return None

        print("      Running GLM-OCR via Ollama REST (page-by-page)...")
        page_texts, failed, skipped_empty, n = [], 0, 0, len(doc)
        tmp = tempfile.mkdtemp(prefix="glmocr_")
        # GLM-OCR is sensitive to image tensor shapes. Normalize each page to a
        # fixed 1024x1024 image before sending to Ollama.
        target_px = 1024
        try:
            from PIL import Image as _PILImage
            _pil_available = True
        except ImportError:
            _pil_available = False
            print("      NOTE: Pillow not installed - using direct fitz normalization")

        def _restart_glm_worker(reason: str = "") -> None:
            reason_msg = f" ({reason})" if reason else ""
            print(f"      Restarting glm-ocr worker{reason_msg}...")
            try:
                subprocess.run(["ollama", "stop", "glm-ocr"], capture_output=True, text=True, timeout=10)
            except Exception:
                pass
            _t.sleep(3)
            ensure_ollama_running()

        def _ocr_payload_from_bytes(img_bytes: bytes) -> bytes:
            img_b64 = base64.b64encode(img_bytes).decode()
            return _js.dumps({
                "model": "glm-ocr",
                "prompt": "Text Recognition: ",
                "images": [img_b64],
                "stream": False,
                # Keep worker warm briefly to avoid repeated load/unload stalls
                # on Windows; crash handling still restarts on bad pages.
                "keep_alive": "30s",
                "options": {"num_ctx": 8192},
            }).encode()

        def _ollama_generate_once(_payload: bytes) -> bytes:
            req = _ur.Request(
                "http://localhost:11434/api/generate",
                data=_payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with _ur.urlopen(req, timeout=180) as r:
                return r.read()

        def _run_ollama_payload(_payload: bytes, page_num: int, attempt: int, timeout_sec: int = 60) -> Tuple[str, str]:
            """Return (text, error_message). Exactly one is non-empty."""
            _pool = _cf.ThreadPoolExecutor(max_workers=1)
            _future = _pool.submit(_ollama_generate_once, _payload)
            try:
                resp_body = _future.result(timeout=timeout_sec)
                resp_json = _js.loads(resp_body)
                if "error" in resp_json:
                    return "", str(resp_json.get("error", "Unknown Ollama error"))
                text = _strip_code_fences(resp_json.get("response", "").strip())
                return text, ""
            except _cf.TimeoutError:
                _future.cancel()
                return "", f"timed out (>{timeout_sec}s)"
            except _ue.HTTPError as _http_exc:
                err_raw = ""
                err_msg = f"HTTP {_http_exc.code}"
                try:
                    err_raw = _http_exc.read().decode("utf-8", errors="replace")
                    err_json = _js.loads(err_raw)
                    err_msg = str(err_json.get("error", err_raw))[:240]
                except Exception:
                    if err_raw:
                        err_msg = err_raw[:240]
                return "", err_msg
            except _ue.URLError as _url_exc:
                return "", f"URL error: {_url_exc.reason}"
            except Exception as _page_exc:
                err = str(_page_exc).strip() or repr(_page_exc)
                return "", err[:240]
            finally:
                _pool.shutdown(wait=False, cancel_futures=True)

        def _is_worker_crash_error(msg: str) -> bool:
            m = (msg or "").lower()
            return ("health resp" in m) or ("connection refused" in m) or ("ggml_assert" in m)

        def _is_likely_empty_page(page_obj) -> bool:
            """Disabled to avoid false skips; keep all pages in OCR pipeline."""
            return False

        def _issue_note() -> str:
            if failed and skipped_empty:
                return f"  ({failed} failed, {skipped_empty} empty skipped)"
            if failed:
                return f"  ({failed} failed)"
            if skipped_empty:
                return f"  ({skipped_empty} empty skipped)"
            return ""

        def _tiled_glm_ocr(page_obj) -> str:
            """GLM-only fallback for problematic pages: OCR 4 tiles and join output."""
            r = page_obj.rect
            mx = (r.x0 + r.x1) / 2.0
            my = (r.y0 + r.y1) / 2.0
            tiles = [
                fitz.Rect(r.x0, r.y0, mx, my),
                fitz.Rect(mx, r.y0, r.x1, my),
                fitz.Rect(r.x0, my, mx, r.y1),
                fitz.Rect(mx, my, r.x1, r.y1),
            ]
            tile_texts = []
            for t_idx, t_rect in enumerate(tiles, start=1):
                tpix = page_obj.get_pixmap(
                    matrix=fitz.Matrix(2, 2),
                    clip=t_rect,
                    colorspace=fitz.csRGB,
                    alpha=False,
                )
                tbytes = tpix.tobytes("png")
                if _pil_available:
                    with _PILImage.open(_io.BytesIO(tbytes)) as _im:
                        _im = _im.convert("RGB").resize((target_px, target_px), _PILImage.BICUBIC)
                        _buf = _io.BytesIO()
                        _im.save(_buf, "PNG")
                        tbytes = _buf.getvalue()
                t_payload = _ocr_payload_from_bytes(tbytes)
                text = ""
                err = ""
                for tile_attempt in range(2):
                    text, err = _run_ollama_payload(t_payload, -1, t_idx, timeout_sec=95)
                    if text:
                        break
                    err_disp = err or "<no error message>"
                    print(f"      GLM tile {t_idx}/4 attempt {tile_attempt + 1} failed: {err_disp}")
                    if _is_worker_crash_error(err):
                        _restart_glm_worker(reason=f"tile {t_idx} attempt {tile_attempt + 1}")
                if text:
                    tile_texts.append(text)
            return "\n\n".join([t for t in tile_texts if t.strip()])

        try:
            for i, page in enumerate(doc):
                print(f"      GLM-OCR page {i+1}/{n}: processing...")

                if _is_likely_empty_page(page):
                    skipped_empty += 1
                    print(f"      GLM-OCR page {i+1}: skipped likely-empty page")
                    if progress is not None:
                        progress.substep(1, f"GLM-OCR — page {i+1}/{n}{_issue_note()}", i + 1, n)
                    if (i + 1) % 5 == 0 or (i + 1) == n:
                        print(f"      GLM-OCR: {i+1}/{n} pages" + _issue_note())
                    continue

                # Render directly at a fixed pixel shape for stable multimodal input.
                rect = page.rect
                sx = target_px / max(float(rect.width), 1.0)
                sy = target_px / max(float(rect.height), 1.0)
                pix = page.get_pixmap(
                    matrix=fitz.Matrix(sx, sy),
                    colorspace=fitz.csRGB,
                    alpha=False,
                )
                img_path = os.path.join(tmp, f"p{i:04d}.png")
                pix.save(img_path)

                # Keep output dimensions consistent even if renderer rounding varies.
                if _pil_available:
                    with _PILImage.open(img_path) as im:
                        if im.size != (target_px, target_px):
                            im_resized = im.resize((target_px, target_px), _PILImage.LANCZOS)
                        else:
                            im_resized = im
                        im_resized.save(img_path, "PNG")

                with open(img_path, "rb") as fh:
                    img_bytes = fh.read()
                os.unlink(img_path)

                def _resized_for_attempt(_bytes: bytes, _attempt_px: int) -> bytes:
                    if (not _pil_available) or (_attempt_px >= target_px):
                        return _bytes
                    try:
                        with _PILImage.open(_io.BytesIO(_bytes)) as _im:
                            _im = _im.convert("RGB").resize((_attempt_px, _attempt_px), _PILImage.BICUBIC)
                            _buf = _io.BytesIO()
                            _im.save(_buf, "PNG")
                            return _buf.getvalue()
                    except Exception:
                        return _bytes

                page_text = ""
                last_err = ""
                crash_retries = 0
                attempt_px_schedule = [target_px, 896, 768]
                for attempt in range(3):
                    attempt_px = attempt_px_schedule[min(attempt, len(attempt_px_schedule) - 1)]
                    attempt_bytes = _resized_for_attempt(img_bytes, attempt_px)
                    payload = _ocr_payload_from_bytes(attempt_bytes)
                    page_text, last_err = _run_ollama_payload(payload, i + 1, attempt + 1, timeout_sec=60)
                    if page_text:
                        break
                    if _is_worker_crash_error(last_err):
                        crash_retries += 1
                    if attempt < 2:
                        err_disp = last_err or "<no error message>"
                        print(
                            f"      GLM-OCR page {i+1} attempt {attempt+1} "
                            f"(px={attempt_px}) failed: {err_disp}"
                        )
                        if _is_worker_crash_error(last_err):
                            _restart_glm_worker(reason=f"page {i+1} attempt {attempt+1}")
                            # Two deterministic crash signatures usually means this page
                            # won't recover as a full image; switch to tiled fallback early.
                            if crash_retries >= 2:
                                print(f"      GLM-OCR page {i+1}: repeated crash signature, switching to tiled fallback")
                                break
                        _t.sleep((attempt + 1) * 5)
                    else:
                        err_disp = last_err or "<no error message>"
                        print(f"      GLM-OCR page {i+1} failed after 3 attempts: {err_disp}")

                if not page_text:
                    err_disp = last_err or "<no error message>"
                    print(
                        f"      GLM-OCR page {i+1}: trying tiled fallback (GLM-only) "
                        f"after page failure: {err_disp}"
                    )
                    # A full-page failure often recovers when OCR is run on smaller tiles,
                    # including timeout-heavy pages that do not surface GGML_ASSERT text.
                    _restart_glm_worker(reason=f"before tiled page {i+1}")
                    page_text = _tiled_glm_ocr(page)
                    if page_text:
                        print(f"      GLM-OCR page {i+1}: tiled fallback succeeded")

                if not page_text:
                    # Final fallback: extract embedded PDF text for this page only.
                    fallback_text = (page.get_text("text") or "").strip()
                    if fallback_text:
                        page_text = fallback_text
                        print(f"      GLM-OCR page {i+1}: used embedded-text fallback")

                if page_text:
                    page_texts.append(page_text)
                else:
                    failed += 1

                if progress is not None:
                    progress.substep(1, f"GLM-OCR — page {i+1}/{n}{_issue_note()}", i + 1, n)
                if (i + 1) % 5 == 0 or (i + 1) == n:
                    print(f"      GLM-OCR: {i+1}/{n} pages" + _issue_note())
        finally:
            doc.close()
            _sh.rmtree(tmp, ignore_errors=True)

        text = "\n\n".join(page_texts)
        if not text.strip():
            print("WARNING: GLM-OCR returned empty on all pages")
            return None
        if failed or skipped_empty:
            issues = []
            if failed:
                issues.append(f"{failed} failed")
            if skipped_empty:
                issues.append(f"{skipped_empty} empty skipped")
            print(f"WARNING: GLM-OCR page outcomes: {', '.join(issues)} out of {n}")
        print(f"OK: Extracted with GLM-OCR ({len(text):,} chars, {len(page_texts)} pages)")
        return text, "GLM-OCR (Ollama)"

    def extract_with_grobid(self, pdf_path: str) -> Optional[Tuple[str, str]]:
        """Extract text via Grobid servers with fallback. Returns (text, method)."""
        if not requests:
            return None

        pdf_size_mb = Path(pdf_path).stat().st_size / 1024 / 1024
        # Large PDFs need more time; cap at 5 minutes
        timeout = min(max(60, int(pdf_size_mb * 10)), 300)

        for grobid_server in self.grobid_servers:
            print(f"      Trying Grobid: {grobid_server} (timeout {timeout}s)...")
            try:
                with open(pdf_path, 'rb') as f:
                    response = requests.post(
                        f"{grobid_server}/api/processFulltextDocument",
                        files={'input': f},
                        timeout=timeout
                    )
                if response.status_code == 200:
                    text, structure = self._parse_grobid_xml(response.text)
                    if text:
                        method = f"Grobid ({grobid_server.split('/')[-1]}) - {structure}"
                        print(f"OK: Extracted with {method}")
                        return text, method
                    else:
                        print(f"WARNING: Grobid returned empty text: {grobid_server} - trying next...")
                else:
                    print(f"WARNING: Grobid HTTP {response.status_code}: {grobid_server} - trying next...")
            except requests.exceptions.Timeout:
                print(f"TIMEOUT: Grobid timeout after {timeout}s: {grobid_server} - trying next...")
                continue
            except requests.exceptions.ConnectionError:
                print(f"WARNING: Grobid unavailable: {grobid_server} - trying next...")
                continue
            except Exception as e:
                print(f"WARNING: Grobid error ({grobid_server}): {str(e)[:50]} - trying next...")
                continue

        return None

    def _parse_grobid_xml(self, xml_text: str) -> Tuple[str, str]:
        """Extract text from GROBID XML response. Returns (text, structure_summary)."""
        try:
            import xml.etree.ElementTree as ET

            namespaces = {
                'tei': 'http://www.tei-c.org/ns/1.0',
                '': 'http://www.tei-c.org/ns/1.0'
            }
            for prefix, uri in namespaces.items():
                ET.register_namespace(prefix, uri)

            root = ET.fromstring(xml_text)
            ns = {'tei': 'http://www.tei-c.org/ns/1.0'}

            content_parts = []
            sections = []

            abstract = root.find('.//tei:abstract', ns)
            if abstract is not None:
                abs_text = self._extract_text_from_element(abstract, ns)
                if abs_text.strip():
                    content_parts.append("## Abstract\n\n" + abs_text)
                    sections.append("abstract")

            body = root.find('.//tei:body', ns)
            if body is not None:
                body_text = self._extract_body_text(body, ns)
                if body_text.strip():
                    content_parts.append(body_text)
                    sections.append("body")

            if not content_parts:
                text_parts = []
                for elem in root.iter():
                    if elem.text and elem.text.strip():
                        text_parts.append(elem.text.strip())
                return '\n\n'.join(text_parts), "fallback"

            full_text = '\n\n'.join(content_parts)
            return full_text, ', '.join(sections) if sections else "partial"

        except Exception as e:
            print(f"WARNING: XML parsing failed: {e}")
            return None, "error"

    def _extract_text_from_element(self, elem, ns: dict) -> str:
        """Extract all text from an element and its children."""
        text_parts = []
        if elem.text and elem.text.strip():
            text_parts.append(elem.text.strip())
        for child in elem.iter():
            if child != elem and child.text and child.text.strip():
                text_parts.append(child.text.strip())
            if child.tail and child.tail.strip() and child != elem:
                text_parts.append(child.tail.strip())
        return ' '.join(text_parts)

    def _extract_body_text(self, body_elem, ns: dict) -> str:
        """Extract body sections with hierarchical structure."""
        content_parts = []

        for div in body_elem.findall('.//tei:div', ns):
            head = div.find('tei:head', ns)
            if head is not None:
                title = self._extract_text_from_element(head, ns).strip()
                if title:
                    content_parts.append(f"## {title}\n")

            for para in div.findall('.//tei:p', ns):
                para_text = self._extract_text_from_element(para, ns).strip()
                if para_text:
                    content_parts.append(para_text)

        if not content_parts:
            for para in body_elem.findall('.//tei:p', ns):
                para_text = self._extract_text_from_element(para, ns).strip()
                if para_text:
                    content_parts.append(para_text)

        return '\n\n'.join(content_parts)

    def extract_text(self, pdf_path: str, output_dir: Path = None,
                     progress=None) -> Tuple[str, str]:
        """Extract text from PDF with fallback chain. Returns (text, method_used).

        Extraction order (auto): glm-ocr -> marker -> grobid
        Override with --extraction glm-ocr|marker|grobid to force a specific method.
        """
        print(f"Extracting text from: {Path(pdf_path).name}")

        # Build the ordered list of methods to try
        if self.extraction == "glm-ocr":
            methods = [("GLM-OCR", self.extract_with_glm_ocr)]
        elif self.extraction == "marker":
            methods = [("marker", self.extract_with_marker)]
        elif self.extraction == "grobid":
            methods = [("Grobid", self.extract_with_grobid)]
        else:
            methods = [
                ("GLM-OCR", self.extract_with_glm_ocr),
                ("marker",  self.extract_with_marker),
                ("Grobid",  self.extract_with_grobid),
            ]

        for name, method_fn in methods:
            if progress:
                progress.substep(1, f"Trying {name}…", 0, 1)
            # GLM-OCR and marker can both report live extraction progress.
            if name in ("GLM-OCR", "marker"):
                result = method_fn(pdf_path, progress=progress)
            else:
                result = method_fn(pdf_path)
            if result:
                text, method = result
                if output_dir:
                    self._save_extracted_text(Path(pdf_path).stem, text, method, output_dir)
                return text, method

        raise ValueError(f"Could not extract text from {pdf_path}. Ensure it's not a scanned image.")

    def _save_extracted_text(self, pdf_name: str, text: str, method: str, output_dir: Path):
        """Save raw extracted text as markdown file with metadata."""
        md_file = output_dir / f"{pdf_name}_extracted.md"
        metadata = f"""---
extraction_method: {method}
date_extracted: {datetime.now().isoformat()}
character_count: {len(text)}
word_count: {len(text.split())}
---

# {pdf_name} - Extracted Text

**Extraction Method**: {method}
**Characters**: {len(text):,}
**Words**: {len(text.split()):,}
**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M')}

---

{text}
"""
        md_file.write_text(metadata, encoding='utf-8')
        print(f"Raw text saved: {md_file.name}")


# ---------------------------------------------------------------------------
# TTS
# ---------------------------------------------------------------------------

class UnifiedSpeechAPI:
    """Unified interface for multiple TTS engines."""

    @staticmethod
    def synthesize_edge_tts(
        text: str,
        output_path: str,
        voice: str = "en-US-AriaNeural",
        timing_path: str = None,
    ) -> bool:
        """Synthesize speech using Edge TTS, chunking large texts automatically."""
        try:
            import asyncio
            import json
            import tempfile
            from edge_tts import Communicate

            chunks = chunk_text_for_tts(text)
            total_chars = len(text)
            print(f"Generating audio with Edge TTS...")
            print(f"   Voice: {voice}")
            print(f"   Text length: {total_chars:,} characters")
            if len(chunks) > 1:
                print(f"   Chunks: {len(chunks)} (large text split at sentence boundaries)")

            all_word_boundaries = []
            chunk_audio_paths = []
            time_offset = 0.0

            async def tts_chunk_async(chunk_text, chunk_path):
                boundaries = []
                communicate = Communicate(text=chunk_text, voice=voice, rate="+20%")
                stream_iter = communicate.stream() if hasattr(communicate, "stream") else communicate
                if not hasattr(stream_iter, "__aiter__"):
                    raise TypeError(
                        "edge-tts stream object is not async iterable; please update edge-tts"
                    )
                with open(chunk_path, "wb") as audio_file:
                    async for item in stream_iter:
                        if item["type"] == "audio":
                            audio_file.write(item["data"])
                        elif item["type"] in ("WordBoundary", "SentenceBoundary"):
                            boundaries.append({
                                "word":      item["text"],
                                "start_sec": item["offset"] / 10_000_000,
                            })
                return boundaries

            import time as _time
            tmp_dir = tempfile.mkdtemp()
            for i, chunk in enumerate(chunks):
                if len(chunks) > 1:
                    print(f"   Processing chunk {i+1}/{len(chunks)} ({len(chunk):,} chars)...")
                chunk_path = os.path.join(tmp_dir, f"chunk_{i:04d}.mp3")
                # Retry up to 3 times per chunk on NoAudioReceived
                for attempt in range(3):
                    try:
                        boundaries = asyncio.run(tts_chunk_async(chunk, chunk_path))
                        break
                    except Exception as exc:
                        if attempt < 2 and "NoAudioReceived" in type(exc).__name__:
                            wait = (attempt + 1) * 5
                            print(f"   WARNING: No audio received (attempt {attempt+1}/3), retrying in {wait}s...")
                            _time.sleep(wait)
                        else:
                            raise
                # Offset timing data by accumulated duration
                for b in boundaries:
                    all_word_boundaries.append({
                        "word":      b["word"],
                        "start_sec": b["start_sec"] + time_offset,
                    })
                chunk_audio_paths.append(chunk_path)
                # Estimate duration offset from last boundary (rough)
                if boundaries:
                    time_offset = all_word_boundaries[-1]["start_sec"] + 0.5
                # Brief pause between chunks to avoid rate limiting
                if i < len(chunks) - 1:
                    _time.sleep(2)

            # Concatenate chunk MP3s into final output
            output_file = Path(output_path)
            with open(output_file, "wb") as out_f:
                for chunk_path in chunk_audio_paths:
                    cp = Path(chunk_path)
                    if cp.exists():
                        out_f.write(cp.read_bytes())
                        cp.unlink()

            # Clean up temp dir
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

            if not output_file.exists() or output_file.stat().st_size == 0:
                print("FAILED: Audio file was not created")
                return False

            file_size = output_file.stat().st_size / 1024 / 1024
            print(f"OK: Audio generated ({output_file.name}, {file_size:.1f} MB)")

            # Save timing sidecar
            if timing_path and all_word_boundaries:
                Path(timing_path).write_text(
                    json.dumps(all_word_boundaries, indent=2), encoding="utf-8"
                )
                print(f"OK: Timing saved ({len(all_word_boundaries):,} words -> {Path(timing_path).name})")

            return True

        except ImportError:
            print("FAILED: edge-tts not found. Install with: pip install edge-tts")
            return False
        except Exception as e:
            print(f"FAILED: Edge TTS error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False

    @staticmethod
    def synthesize_coqui(text: str, output_path: str, speaker: str = "p225") -> bool:
        """Synthesize speech using Coqui TTS (local)."""
        try:
            from TTS.api import TTS

            print(f"Generating audio with Coqui TTS...")
            tts = TTS(model_name="tts_models/en/ljspeech/glow-tts",
                      progress_bar=True, gpu=False)
            tts.tts_to_file(text=text, file_path=output_path)

            output_file = Path(output_path)
            if output_file.exists():
                file_size = output_file.stat().st_size / 1024 / 1024
                print(f"OK: Audio generated ({Path(output_path).name}, {file_size:.1f} MB)")
                return True
            else:
                print("FAILED: Audio file was not created")
                return False

        except ImportError:
            print("FAILED: Coqui TTS not found. Install with: pip install TTS")
            return False
        except Exception as e:
            print(f"FAILED: Coqui TTS error: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            return False


# ---------------------------------------------------------------------------
# Obsidian note generator
# ---------------------------------------------------------------------------

def create_obsidian_note(
    pdf_stem: str,
    pdf_name: str,
    audio_filename: str,
    extracted_text: str,
    extraction_method: str,
    tts_method: str,
    output_dir: Path,
) -> Path:
    """Create a YouTube-style Obsidian note for a converted PDF."""

    note_path = output_dir / f"{pdf_stem}.md"
    today = datetime.now().strftime("%Y-%m-%d")
    word_count = len(extracted_text.split())

    # Vault-relative path so AUDIO_PLAYER can find the file
    media_folder = "09_audio_video_notes/pdf_audio_outputs"

    title_yaml = pdf_stem.replace('"', "'")

    note_content = f"""---
title: "{title_yaml}"
type: "pdf-audio"
date_added: {today}
source_pdf: "{pdf_name}"
media_folder: "{media_folder}"
audio_file: "{audio_filename}"
extraction_method: "{extraction_method}"
tts_method: "{tts_method}"
word_count: {word_count}
character_count: {len(extracted_text)}
status: "to_listen"
---

# {pdf_stem}

| | |
|---|---|
| **Source** | {pdf_name} |
| **Words** | {word_count:,} |
| **Extracted via** | {extraction_method} |
| **Audio via** | {tts_method} |
| **Date** | {today} |

---

## Listen

{AUDIO_PLAYER}

{TIMESTAMP_BUTTON}

*[🔍 Extract transcript for timestamps](obsidian://shell-commands?vault=obsidian&execute=extract-transcript-all)*

{TRANSCRIBE_BUTTON}

---

## Notes

<!-- Add your notes here as you listen -->

---

## Key Points

-

---

## Action Items

- [ ]

---

## Timestamps

---

## Full Text

{extracted_text}
"""

    note_path.write_text(note_content, encoding='utf-8')
    print(f"OK: Note created: {note_path.name}")
    return note_path


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def ensure_ollama_running() -> bool:
    """Start Ollama if not already running. Returns True if reachable."""
    import urllib.request as _ur
    import subprocess as _sp
    import time as _t
    import os as _os
    try:
        _ur.urlopen("http://localhost:11434", timeout=2)
        return True
    except Exception:
        pass
    ollama_exe = "ollama"
    for candidate in [
        _os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
        r"C:\Program Files\Ollama\ollama.exe",
    ]:
        if _os.path.exists(candidate):
            ollama_exe = candidate
            break
    try:
        _sp.Popen(
            [ollama_exe, "serve"],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
            creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0),
        )
        for _ in range(10):
            _t.sleep(1)
            try:
                _ur.urlopen("http://localhost:11434", timeout=1)
                return True
            except Exception:
                pass
    except FileNotFoundError:
        print("WARNING: ollama not found. Install from https://ollama.ai")
    return False


def process_pdf(
    pdf_path: Path,
    output_audio_dir: Path,
    output_notes_dir: Path,
    output_extracted_dir: Path,
    vault: Path,
    tts_method: str = "edge-tts",
    grobid_server: str = None,
    extraction: str = "auto",
    marker_mode: str = "quality",
    batch_index: int = 0,
    batch_total: int = 1,
    completed_log: list = None,
) -> bool:
    """Process a single PDF file."""

    import time
    start_time = time.time()
    progress = Progress(vault, pdf_path.name,
                    batch_index=batch_index,
                    batch_total=batch_total,
                    completed_log=completed_log)

    print(f"Processing: {pdf_path.name}")

    # 1. Extract text
    progress.step(1)
    print(f"[1/4] Extracting text from PDF...")
    extractor = PDFExtractor(
        grobid_server=grobid_server,
        extraction=extraction,
        marker_mode=marker_mode,
    )
    try:
        extracted_text, extraction_method = extractor.extract_text(
            str(pdf_path), output_extracted_dir, progress=progress
        )
        elapsed = time.time() - start_time
        print(f"      OK: Extraction complete ({elapsed:.1f}s) - {extraction_method}")
    except Exception as e:
        progress.error("Extracting text", str(e))
        print(f"      FAILED: Extraction failed: {e}")
        return False

    # 2. Prepare text for TTS (strip markdown headers + collapse whitespace)
    progress.step(2)
    print(f"[2/4] Preparing text for TTS...")
    tts_text = clean_text_for_tts(extracted_text)
    print(f"      OK: {len(tts_text):,} characters ready")

    # 3. Generate audio
    progress.step(3, f"{len(tts_text):,} characters")
    print(f"[3/4] Converting text to speech...")
    audio_filename = pdf_path.stem + ".mp3"
    audio_path = output_audio_dir / audio_filename
    timing_filename = pdf_path.stem + "_timing.json"
    timing_path = output_audio_dir / timing_filename

    if tts_method == "edge-tts":
        success = UnifiedSpeechAPI.synthesize_edge_tts(
            tts_text, str(audio_path), timing_path=str(timing_path)
        )
    else:
        success = UnifiedSpeechAPI.synthesize_coqui(tts_text, str(audio_path))

    if not success:
        progress.error("Converting text to speech", "TTS synthesis failed")
        print("      FAILED: TTS synthesis failed")
        return False

    # 4. Create Obsidian note
    progress.step(4)
    print(f"[4/4] Creating Obsidian note...")
    try:
        create_obsidian_note(
            pdf_stem=pdf_path.stem,
            pdf_name=pdf_path.name,
            audio_filename=audio_filename,
            extracted_text=extracted_text,
            extraction_method=extraction_method,
            tts_method=tts_method,
            output_dir=output_notes_dir,
        )
    except Exception as e:
        progress.error("Creating Obsidian note", str(e))
        print(f"      FAILED: Note generation failed: {e}")
        return False

    elapsed = time.time() - start_time
    progress.done(pdf_path.stem, elapsed)
    print(f"COMPLETE: {pdf_path.name} ({elapsed:.1f}s)")
    return True


# ---------------------------------------------------------------------------
# Home note helpers
# ---------------------------------------------------------------------------

def add_listen_task(home_note: str, pdf_stem: str, today: str):
    """Insert a Listen task into the ## Watchlist section of the home note."""
    task_line = f"- [ ] Listen [[{pdf_stem}]] 📅 {today}"
    try:
        with open(home_note, encoding="utf-8") as f:
            home = f.read()

        marker = "## Watchlist"
        if marker in home:
            home = home.replace(
                marker + "\n",
                marker + "\n\n" + task_line + "\n",
                1,
            )
        else:
            home = home + f"\n\n{marker}\n\n{task_line}\n"

        with open(home_note, "w", encoding="utf-8") as f:
            f.write(home)

        print(f"OK: Task added to home note: Listen {pdf_stem}")
    except OSError as e:
        print(f"WARNING: Could not update home note: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert PDF to audiobook with YouTube-style Obsidian note",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py -3 pdf_to_speech.py --vault "C:\\vault" --note "C:\\vault\\09_audio_video_notes\\01 - Home_Audio_Video.md"
  py -3 pdf_to_speech.py --vault "C:\\vault" --note "..." --pdf "paper.pdf"
  py -3 pdf_to_speech.py --vault "C:\\vault" --note "..." --tts coqui
        """
    )
    parser.add_argument("--vault", required=True, help="Absolute path to Obsidian vault root")
    parser.add_argument("--note",  required=True, help="Absolute path to home note")
    parser.add_argument("--tts",   choices=["edge-tts", "coqui"], default="edge-tts")
    parser.add_argument("--version", action="version", version=f"pdf_to_speech.py v{SCRIPT_VERSION}")
    parser.add_argument("--grobid", default=None,
                        help="Grobid server URL, 'local', or 'skip'")
    parser.add_argument("--all", action="store_true", help="Convert all PDFs in pdfs_to_convert/")
    parser.add_argument("--extraction", choices=["auto", "glm-ocr", "marker", "grobid"],
                        default="auto",
                        help="Extraction method: auto (glm-ocr->marker->grobid), glm-ocr, marker, or grobid")
    parser.add_argument("--marker-mode", choices=["quality", "fast"], default="quality",
                        help="Marker mode when using marker extraction: quality (default) or fast")
    parser.add_argument("--pdf",   type=str, default=None,
                        help="PDF filename (just the name, not full path) or full path")

    args = parser.parse_args()

    vault = Path(args.vault.rstrip("\\/"))
    base_dir = vault / "09_audio_video_notes"
    input_dir = base_dir / "pdfs_to_convert"
    output_audio_dir = base_dir / "pdf_audio_outputs"
    output_notes_dir = base_dir          # Notes go directly into 09_audio_video_notes/
    output_extracted_dir = base_dir / "pdf_extracted_text"
    pending_file = vault / "99 - System" / "pdf_to_convert_pending.txt"

    output_audio_dir.mkdir(exist_ok=True)
    output_extracted_dir.mkdir(exist_ok=True)

    home_note_path = args.note.rstrip(" )")

    # Collect PDF list
    if getattr(args, "all", False):
        pdf_files = sorted(input_dir.glob("*.pdf"))
        if not pdf_files:
            print("INFO: No PDFs found in pdfs_to_convert/")
            return 0
        print(f"Batch mode: {len(pdf_files)} PDF(s) queued.")
        pending_file.write_text("", encoding="utf-8")
    elif args.pdf:
        pdf_arg = Path(args.pdf)
        pdf_files = [pdf_arg if pdf_arg.is_absolute() else input_dir / pdf_arg]
    elif pending_file.exists():
        pdf_name = pending_file.read_text(encoding="utf-8").strip()
        if not pdf_name:
            print("FAILED: pdf_to_convert_pending.txt is empty.")
            return 1
        if pdf_name == "__ALL__":
            pdf_files = sorted(input_dir.glob("*.pdf"))
            if not pdf_files:
                print("INFO: No PDFs found in pdfs_to_convert/")
                pending_file.write_text("", encoding="utf-8")
                return 0
            print(f"Batch mode (pending token): {len(pdf_files)} PDF(s) queued.")
        else:
            pdf_files = [input_dir / pdf_name]
        pending_file.write_text("", encoding="utf-8")
    else:
        print("FAILED: No PDF specified and pdf_to_convert_pending.txt is empty.")
        return 1

    import time as _bt
    archive_dir = input_dir / "_processed"
    archive_dir.mkdir(exist_ok=True)
    results, completed_log = [], []
    today = datetime.now().strftime("%Y-%m-%d")

    for idx, pdf_path in enumerate(pdf_files):
        if not pdf_path.exists():
            print(f"SKIPPED: {pdf_path.name} not found")
            results.append((pdf_path.name, False))
            completed_log.append((pdf_path.name, 0, False))
            continue
        if len(pdf_files) > 1:
            print(f"\n{'='*60}\nPDF {idx+1}/{len(pdf_files)}: {pdf_path.name}\n{'='*60}")
        t0 = _bt.time()
        success = process_pdf(
            pdf_path=pdf_path,
            output_audio_dir=output_audio_dir,
            output_notes_dir=output_notes_dir,
            output_extracted_dir=output_extracted_dir,
            vault=vault,
            tts_method=args.tts,
            grobid_server=args.grobid,
            extraction=args.extraction,
            marker_mode=args.marker_mode,
            batch_index=idx,
            batch_total=len(pdf_files),
            completed_log=completed_log,
        )
        elapsed = _bt.time() - t0
        if success:
            add_listen_task(home_note_path, pdf_path.stem, today)
            dest = archive_dir / pdf_path.name
            try:
                if dest.exists():
                    dest.unlink()
                if pdf_path.exists():
                    pdf_path.rename(dest)
                    print(f"OK: PDF archived to: _processed/{pdf_path.name}")
                else:
                    print(
                        f"WARNING: Source PDF missing before archive step: {pdf_path.name} "
                        f"(conversion already completed)"
                    )
            except OSError as e:
                print(
                    f"WARNING: Could not archive PDF {pdf_path.name}: {e} "
                    f"(conversion already completed)"
                )
        results.append((pdf_path.name, success))
        completed_log.append((pdf_path.name, elapsed, success))

    n_ok = sum(s for _, s in results)
    if len(results) > 1:
        print(f"\n{'='*60}\nBATCH COMPLETE: {n_ok}/{len(results)} succeeded")
        for name, ok in results:
            print(f"  {'OK' if ok else 'FAILED':6s}  {name}")
        print(f"{'='*60}")
        prog_path = vault / "99 - System" / "pdf_convert_progress.md"
        lines_out = [f"### Batch complete: {n_ok}/{len(results)} succeeded", ""]
        total_e = sum(e for _, e, _ in completed_log)
        for name, elapsed, ok in completed_log:
            lines_out.append(f"{'OK' if ok else 'FAILED'}  {name}  ({elapsed:.0f}s)")
        lines_out += ["", f"Total time: {total_e:.0f}s"]
        try:
            prog_path.write_text("\n".join(lines_out) + "\n", encoding="utf-8")
        except Exception:
            pass

    return 0 if all(s for _, s in results) else 1


if __name__ == "__main__":
    sys.exit(main())
