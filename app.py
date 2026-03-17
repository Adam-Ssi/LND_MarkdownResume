"""
Markdown Resume Builder — FastAPI backend
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown2
import weasyprint
from fastapi import FastAPI, Form, HTTPException
from fastapi.requests import Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
THEMES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Markdown Resume Builder", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(THEMES_DIR))

AVAILABLE_THEMES = ["modern", "classic", "academic"]

MARKDOWN_EXTRAS = [
    "tables",
    "fenced-code-blocks",
    "strike",
    "smarty-pants",
    "break-on-newline",
]

# ---------------------------------------------------------------------------
# Pre-loaded resume templates
# ---------------------------------------------------------------------------
PROFESSIONAL_TEMPLATE = """\
# Alex Johnson

**Email:** alex@example.com | **Phone:** (555) 234-5678 | **Location:** New York, NY
**LinkedIn:** linkedin.com/in/alexjohnson | **GitHub:** github.com/alexjohnson

---

## Summary

Experienced full-stack engineer with 6+ years building scalable web applications and
cloud infrastructure. Passionate about developer tooling, clean architecture, and
shipping products users love.

---

## Experience

### Senior Software Engineer — TechCorp
*March 2021 – Present | New York, NY*

- Architected event-driven microservices platform handling 50 M+ events/day
- Reduced CI/CD pipeline duration by 45 % via parallelisation and caching strategies
- Led a team of 4 engineers; introduced bi-weekly architecture review sessions
- Drove adoption of infrastructure-as-code, cutting environment setup time from days to hours

### Software Engineer — StartupXYZ
*June 2018 – February 2021 | San Francisco, CA*

- Built customer-facing React dashboard adopted by 10,000+ users within 3 months
- Designed RESTful APIs serving both mobile and web clients (99.9 % uptime SLA)
- Migrated legacy MySQL monolith to PostgreSQL with zero downtime

---

## Education

### B.S. Computer Science — University of Michigan
*2014 – 2018*

GPA: 3.7 / 4.0 | Dean's List (6 semesters)

---

## Skills

**Languages:** Python, TypeScript, Go, SQL, Bash
**Frameworks:** FastAPI, React, Next.js, Node.js
**Infrastructure:** AWS, Docker, Kubernetes, Terraform, GitHub Actions
**Databases:** PostgreSQL, Redis, MongoDB, Elasticsearch

---

## Projects

### ResumeBuilder *(github.com/alexjohnson/resumebuilder)*
Open-source Markdown resume generator with theme support. 800+ GitHub stars.

### DataFlow CLI *(github.com/alexjohnson/dataflow)*
CLI tool for streaming ETL pipelines with pluggable connectors.
"""

ACADEMIC_TEMPLATE = """\
# Dr. Maria Chen

**Email:** maria.chen@university.edu | **Website:** mariac.academic.edu
**Phone:** (555) 876-5432 | **Location:** Cambridge, MA

---

## Research Interests

Computational Biology, Machine Learning for Genomics, Single-Cell Sequencing Analysis

---

## Education

### Ph.D. Computational Biology — MIT
*2017 – 2023*

Dissertation: *"Deep Learning Approaches to Single-Cell RNA Sequencing Integration"*
Advisor: Prof. Eric Lander

### B.S. Bioinformatics — UC San Diego
*2013 – 2017*

GPA: 3.95 / 4.0 | Valedictorian

---

## Publications

### "Scalable integration of scRNA-seq data using deep variational autoencoders" *(2023)*
*Chen, M., Park, J., Williams, R.* — **Nature Methods** | [doi:10.xxxx](#)

### "Transfer learning for cross-study single-cell annotation" *(2022)*
*Chen, M., Lander, E.* — **Cell Systems** | [doi:10.xxxx](#)

### "Benchmark analysis of batch correction methods in scRNA-seq" *(2021)*
*Chen, M., Zhou, L., Lander, E.* — **Genome Biology** | [doi:10.xxxx](#)

---

## Experience

### Postdoctoral Fellow — Broad Institute of MIT and Harvard
*September 2023 – Present | Cambridge, MA*

- Developing computational methods for multi-modal single-cell data integration
- Leading collaboration between 3 research groups on pan-cancer atlas project

### Research Intern — Google DeepMind
*Summer 2022 | London, UK*

- Applied protein structure prediction models to drug target identification
- Co-authored internal technical report adopted by the AlphaFold team

---

## Teaching

### Teaching Assistant — MIT 7.91J (Computational & Systems Biology)
*Fall 2019, Fall 2020*

- Developed new problem sets on sequence alignment and phylogenetics
- Received 4.8 / 5.0 teaching evaluation score

---

## Awards & Honors

- NIH F31 Ruth L. Kirschstein NRSA Fellowship (2020–2023)
- MIT Presidential Fellowship (2017)
- Nature Methods Best Paper Award (2023)
- Cold Spring Harbor Laboratory Scholar (2021)

---

## Software

**scIntegrate** *(github.com/mariac/scintegrate)* — Python toolkit for single-cell data integration. 1,200+ stars, 85 citations.
**BioML** *(github.com/mariac/bioml)* — Benchmarking suite for ML models on genomic data.
"""

SAMPLE_TEMPLATES: dict[str, str] = {
    "professional": PROFESSIONAL_TEMPLATE,
    "academic": ACADEMIC_TEMPLATE,
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_theme_css(theme: str) -> str:
    """Read a theme CSS file; return empty string if not found."""
    css_path = THEMES_DIR / f"{theme}.css"
    if css_path.exists():
        return css_path.read_text(encoding="utf-8")
    return ""


def _strip_import_rules(css: str) -> str:
    """Remove @import lines so WeasyPrint doesn't make external network calls."""
    return re.sub(r"@import\s+[^;]+;", "", css)


def _build_html(body_html: str, css: str, *, for_print: bool = False) -> str:
    """Wrap rendered Markdown body in a complete HTML document with injected CSS."""
    if for_print:
        css = _strip_import_rules(css)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Resume</title>
  <style>
{css}
  </style>
</head>
<body>
{body_html}
</body>
</html>"""


def _render_markdown(text: str) -> str:
    return str(markdown2.markdown(text, extras=MARKDOWN_EXTRAS))


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "themes": AVAILABLE_THEMES},
    )


@app.post("/preview", response_class=HTMLResponse)
async def preview(
    markdown_text: str = Form(""),
    theme: str = Form("modern"),
) -> HTMLResponse:
    if theme not in AVAILABLE_THEMES:
        theme = "modern"
    body_html = _render_markdown(markdown_text)
    css = _load_theme_css(theme)
    full_html = _build_html(body_html, css, for_print=False)
    return HTMLResponse(content=full_html)


@app.post("/export")
async def export_pdf(
    markdown_text: str = Form(...),
    theme: str = Form("modern"),
) -> Response:
    if theme not in AVAILABLE_THEMES:
        theme = "modern"
    body_html = _render_markdown(markdown_text)
    css = _load_theme_css(theme)
    full_html = _build_html(body_html, css, for_print=True)

    pdf_bytes: bytes = weasyprint.HTML(
        string=full_html,
        base_url=str(BASE_DIR),
    ).write_pdf()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume.pdf"},
    )


@app.get("/template/{name}")
async def get_template(name: str) -> JSONResponse:
    content = SAMPLE_TEMPLATES.get(name)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Template '{name}' not found")
    return JSONResponse({"content": content})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


# ---------------------------------------------------------------------------
# Streamlit proxy compatibility stubs
# Some hosting environments (VS Code ports, Streamlit sharing proxies) probe
# these endpoints expecting a Streamlit app.  Return plausible responses so
# the proxy stops retrying and the logs stay clean.
# ---------------------------------------------------------------------------
@app.get("/_stcore/health")
async def stcore_health() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/_stcore/host-config")
async def stcore_host_config() -> JSONResponse:
    return JSONResponse({"allowedOrigins": ["*"], "useExternalAuthToken": False})


# ---------------------------------------------------------------------------
# Dev entry-point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8501, reload=True)
