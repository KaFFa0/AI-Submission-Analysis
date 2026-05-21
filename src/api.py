import os
from typing import List, Optional
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
import uvicorn

load_dotenv()

from src.AI_review import (
    RepoAnalysisConfig,
    analyze_submission_text,
    analyze_repository_url,
)


def get_config() -> RepoAnalysisConfig:
    """Create RepoAnalysisConfig from environment variables with sensible defaults."""
    return RepoAnalysisConfig(
        api_base_url=os.getenv("API_BASE_URL", "https://api.mistral.ai/v1"),
        api_key=os.getenv("API_KEY", ""),
        api_model_name=os.getenv("API_MODEL_NAME", "open-mistral-7b"),
        embedding_model_name=os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1200")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "360")),
        top_k_file_vector=int(os.getenv("TOP_K_FILE_VECTOR", "8")),
        top_k_file_bm25=int(os.getenv("TOP_K_FILE_BM25", "8")),
        top_k_chunk_vector=int(os.getenv("TOP_K_CHUNK_VECTOR", "18")),
        top_k_chunk_bm25=int(os.getenv("TOP_K_CHUNK_BM25", "18")),
        top_k_final_context=int(os.getenv("TOP_K_FINAL_CONTEXT", "12")),
        top_k_pinned=int(os.getenv("TOP_K_PINNED", "2")),
        max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "512")),
        temperature=float(os.getenv("TEMPERATURE", "0.1")),
        persist_directory=os.getenv("PERSIST_DIRECTORY", None),
        chroma_collection_prefix=os.getenv("CHROMA_COLLECTION_PREFIX", "repo_analysis"),
        ignored_dirs=None, 
        max_file_doc_chars=int(os.getenv("MAX_FILE_DOC_CHARS", "10000")),
        max_notebook_cell_chars=int(os.getenv("MAX_NOTEBOOK_CELL_CHARS", "4000")),
        max_notebook_output_chars=int(os.getenv("MAX_NOTEBOOK_OUTPUT_CHARS", "2000")),
        max_docs_per_path=int(os.getenv("MAX_DOCS_PER_PATH", "2")),
    )


CONFIG = get_config()

app = FastAPI(
    title="Repository & Text Analysis API",
    description="Analyze GitHub repositories or free‑text submissions against custom criteria",
    version="1.0.0",
)


class CriterionItem(BaseModel):
    id: str
    description: str


class TextAnalysisRequest(BaseModel):
    title: str = Field(..., description="Title or identifier of the submission")
    textContent: str = Field(..., description="The text content to analyze")
    criteria: List[CriterionItem] = Field(..., description="List of criteria to evaluate")


class RepoAnalysisRequest(BaseModel):
    repo_url: str = Field(..., description="GitHub repository URL (https://github.com/owner/repo)")
    criteria: List[CriterionItem] = Field(..., description="List of criteria to evaluate")


class EvidenceItem(BaseModel):
    path: Optional[str] = None
    part: Optional[str] = None
    chunk_index: Optional[int] = None
    quote: str
    why: Optional[str] = None


class AnalysisResult(BaseModel):
    criterion_id: str
    criterion_description: str
    score: int
    answer: str
    evidence: List[EvidenceItem]
    confidence: float


@app.get("/health")
def health_check():
    return {"status": "ok", "config": {"api_model": CONFIG.api_model_name}}

@app.post("/analyze/text", response_model=List[AnalysisResult])
async def analyze_text(request: TextAnalysisRequest):
    """
    Analyze a free‑text submission (e.g., a solution description, report, or any textual input)
    against the provided criteria.
    """
    try:
        criteria_dicts = [c.model_dump() for c in request.criteria]

        results = analyze_submission_text(
            title=request.title,
            text_content=request.textContent,
            criteria=criteria_dicts,
            config=CONFIG,
        )
        return [AnalysisResult(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/analyze/repository", response_model=List[AnalysisResult])
async def analyze_repository(request: RepoAnalysisRequest):
    """
    Analyze a public GitHub repository (cloned temporarily) against the provided criteria.
    """
    try:
        criteria_dicts = [c.model_dump() for c in request.criteria]

        results = analyze_repository_url(
            repo_url=request.repo_url,
            criteria=criteria_dicts,
            config=CONFIG,
        )
        return [AnalysisResult(**r) for r in results]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Repository analysis failed: {str(e)}")


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.api:app", host="0.0.0.0", port=port, reload=False)
