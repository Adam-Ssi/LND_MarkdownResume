# ResumerBuilder

A lightweight, browser-based Markdown resume editor with live preview, multiple themes, and PDF export. Write your resume in Markdown, see it rendered in real time, and download a polished PDF.

## Features

- **Live Preview** — Debounced rendering (400ms) as you type, displayed in a sandboxed iframe
- **Multiple Themes** — Choose from Modern, Classic, or Academic resume styles
- **PDF Export** — High-quality PDF generation via WeasyPrint
- **Sample Templates** — Load a pre-built Professional or Academic resume to get started
- **Session Persistence** — Content and theme selection auto-saved to `localStorage`
- **Word Counter** — Real-time word count in the toolbar
- **Synchronized Scroll** — Editor scroll position mirrors the preview pane
- **Responsive Layout** — Side-by-side editor/preview on desktop, stacked on mobile

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | Python / FastAPI / Uvicorn |
| Markdown parsing | markdown2 |
| PDF generation | WeasyPrint |
| Templating | Jinja2 |
| Frontend | Vanilla JS, HTML5, CSS3 |

## Setup

### Prerequisites

- Python 3.10+
- WeasyPrint system dependencies: `pango`, `cairo` (required for PDF rendering)

### Install

```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Run

```bash
python app.py
```

The app runs at `http://localhost:8501`.

## Project Structure

```
ResumerBuilder/
├── app.py                  # FastAPI backend — routes, Markdown processing, PDF export
├── requirements.txt
├── templates/
│   ├── index.html          # Main UI (split-pane editor + preview)
│   ├── modern.css          # Modern theme (sans-serif, blue accent)
│   ├── classic.css         # Classic theme (serif, traditional)
│   └── academic.css        # Academic theme (research-focused)
└── static/
    ├── editor.js           # Frontend logic (debounce, localStorage, scroll sync)
    └── app.css             # Editor UI chrome styles
```

## How It Works

1. Write Markdown in the left pane
2. The frontend POSTs to `/preview` on each keystroke (debounced)
3. The backend converts Markdown → HTML, injects the selected theme CSS, and returns a complete HTML document
4. The preview iframe renders the styled HTML
5. Click **Download PDF** to POST to `/export`, which runs WeasyPrint and streams back a `.pdf` file

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Serve the editor UI |
| `POST` | `/preview` | Render Markdown to themed HTML |
| `POST` | `/export` | Generate and download a PDF |
| `GET` | `/template/{name}` | Load a sample template (`professional`, `academic`) |
