"""FastAPI server for OpenDNA.

Endpoints: /, /api/panels, /api/analyze, /api/analyze-stream, /api/update-db.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from importlib.resources import files
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from opendna.analyzer import analyze
from opendna.annotations import annotate, load_clinvar, load_pharmgkb
from opendna.annotations.updater import refresh
from opendna.llm import get_provider
from opendna.panels import load_panels
from opendna.parser import parse_23andme
from opendna.report import render_report

logger = logging.getLogger("opendna.server")

app = FastAPI(title="OpenDNA", version="0.1.0")


class LLMConfig(BaseModel):
    provider: str
    model: str
    api_key: str


class AnalyzeRequest(BaseModel):
    file_path: str
    selected_panels: list[str] | None = None
    llm: LLMConfig | None = None


_static_dir = Path(str(files("opendna.web").joinpath("static")))
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")


@app.get("/")
def root() -> FileResponse:
    return FileResponse(_static_dir / "index.html")


@app.get("/api/panels")
def list_panels() -> dict[str, Any]:
    return {
        "panels": [
            {"id": p.id, "name": p.name, "description": p.description, "snp_count": len(p.snps)}
            for p in load_panels()
        ]
    }


@app.post("/api/analyze")
def analyze_endpoint(req: AnalyzeRequest) -> JSONResponse:
    path = Path(req.file_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail=f"File not found: {req.file_path}")

    try:
        parsed = parse_23andme(path)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Parse error: {exc}") from exc

    panels = load_panels()
    selected = set(req.selected_panels) if req.selected_panels else None
    findings = analyze(parsed, panels, selected_panel_ids=selected)
    findings = annotate(findings, load_clinvar(), load_pharmgkb())

    prose: str | None = None
    if req.llm is not None:
        logger.info("Invoking LLM provider=%s model=%s", req.llm.provider, req.llm.model)
        try:
            provider = get_provider(req.llm.provider, api_key=req.llm.api_key, model=req.llm.model)
            prose = provider.interpret(findings)
        except Exception as exc:
            logger.exception("LLM synthesis failed")
            raise HTTPException(status_code=502, detail=f"LLM provider error: {exc}") from exc

    bundle = render_report(findings, llm_prose=prose)
    return JSONResponse({
        "report_html": bundle.html,
        "report_json": bundle.json_payload,
    })


def _sse_event(event: str, **data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _analyze_stream_generator(req: AnalyzeRequest) -> Iterator[str]:
    try:
        yield _sse_event("progress", stage="validate", message="Validating file path", pct=5)
        path = Path(req.file_path)
        if not path.exists():
            yield _sse_event("error", detail=f"File not found: {req.file_path}")
            return

        yield _sse_event("progress", stage="parse", message="Parsing DNA file", pct=12)
        try:
            parsed = parse_23andme(path)
        except Exception as exc:
            yield _sse_event("error", detail=f"Parse error: {exc}")
            return
        yield _sse_event(
            "progress", stage="parse",
            message=f"Parsed {len(parsed):,} SNPs from file", pct=30,
        )

        yield _sse_event(
            "progress", stage="analyze",
            message="Matching panels against your genotypes", pct=42,
        )
        panels = load_panels()
        selected = set(req.selected_panels) if req.selected_panels else None
        findings = analyze(parsed, panels, selected_panel_ids=selected)
        matched = sum(1 for f in findings if f.genotype is not None)
        yield _sse_event(
            "progress", stage="analyze",
            message=f"Analyzed {len(findings)} target SNPs ({matched} present)",
            pct=55,
        )

        yield _sse_event(
            "progress", stage="annotate",
            message="Joining ClinVar + PharmGKB annotations", pct=62,
        )
        findings = annotate(findings, load_clinvar(), load_pharmgkb())

        prose: str | None = None
        if req.llm is not None:
            yield _sse_event(
                "progress", stage="llm",
                message=f"Calling {req.llm.provider} ({req.llm.model}) — this may take 10-30s",
                pct=68,
            )
            try:
                provider = get_provider(
                    req.llm.provider,
                    api_key=req.llm.api_key,
                    model=req.llm.model,
                )
                prose = provider.interpret(findings)
                yield _sse_event("progress", stage="llm", message="AI synthesis received", pct=90)
            except Exception as exc:
                logger.exception("LLM synthesis failed")
                yield _sse_event("error", detail=f"LLM provider error: {exc}")
                return

        yield _sse_event("progress", stage="render", message="Rendering report", pct=95)
        bundle = render_report(findings, llm_prose=prose)
        yield _sse_event(
            "complete", pct=100,
            report_html=bundle.html,
            report_json=bundle.json_payload,
        )
    except Exception as exc:
        logger.exception("Stream failed unexpectedly")
        yield _sse_event("error", detail=f"{type(exc).__name__}: {exc}")


@app.post("/api/analyze-stream")
def analyze_stream_endpoint(req: AnalyzeRequest) -> StreamingResponse:
    return StreamingResponse(
        _analyze_stream_generator(req),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/api/update-db")
def update_db() -> JSONResponse:
    return JSONResponse(refresh())
