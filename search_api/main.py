import os
import pickle
from typing import List

import numpy as np
import uvicorn
from fastapi import FastAPI, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastembed import TextEmbedding
from pydantic import BaseModel

app = FastAPI(title="Local File Search")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home():
    """Serve the simple browser UI instead of making people use curl/Swagger."""
    return FileResponse(os.path.join(STATIC_DIR, "index.html"))

# fastembed uses ONNX Runtime instead of PyTorch — much smaller install,
# no compiled CUDA headers, and critically: no Windows long-path issues
# during install, which torch is prone to.
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Default: a hidden folder in the user's home directory, so the index
# persists regardless of which folder someone runs the command from.
# Overridable via env var — Docker setups point this at a mounted volume.
DEFAULT_INDEX_DIR = os.path.join(os.path.expanduser("~"), ".local_file_search")
INDEX_PATH = os.environ.get("INDEX_PATH", os.path.join(DEFAULT_INDEX_DIR, "index.pkl"))

model = TextEmbedding(model_name=MODEL_NAME)


def embed(text: str) -> np.ndarray:
    """fastembed's .embed() returns a generator — pull the single result out."""
    return next(model.embed([text]))


class IndexRequest(BaseModel):
    folder_path: str
    extensions: List[str] = [".txt", ".md"]


def load_index() -> dict:
    """Index format: { file_path: {"snippet": str, "embedding": np.ndarray} }"""
    if os.path.exists(INDEX_PATH):
        with open(INDEX_PATH, "rb") as f:
            return pickle.load(f)
    return {}


def save_index(index: dict) -> None:
    directory = os.path.dirname(INDEX_PATH)
    if directory:
        os.makedirs(directory, exist_ok=True)
    with open(INDEX_PATH, "wb") as f:
        pickle.dump(index, f)


@app.post("/index")
def index_folder(req: IndexRequest):
    """Walk a folder, embed every matching text file, save the index to disk."""

    # Fail loudly instead of silently returning 0 for a bad path.
    if not os.path.exists(req.folder_path):
        return {
            "indexed_files": 0,
            "error": f"Path does not exist: '{req.folder_path}'. If you're running "
                     f"this via Docker, remember your real folder needs to be under "
                     f"the mounted path (e.g. /host/...). If running directly, use "
                     f"the normal path on your computer.",
        }
    if not os.path.isdir(req.folder_path):
        return {
            "indexed_files": 0,
            "error": f"'{req.folder_path}' exists but is not a folder.",
        }

    index = load_index()
    indexed = 0
    scanned = 0
    empty_count = 0
    unreadable_count = 0
    skipped_extensions = set()

    for root, _, files in os.walk(req.folder_path):
        for fname in files:
            scanned += 1
            if not any(fname.endswith(ext) for ext in req.extensions):
                ext = os.path.splitext(fname)[1] or "(no extension)"
                skipped_extensions.add(ext)
                continue

            path = os.path.join(root, fname)
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
            except OSError:
                unreadable_count += 1
                continue

            if not text.strip():
                empty_count += 1
                continue

            # Store filename and content as SEPARATE embeddings, so search can
            # target either one independently instead of one blended vector.
            name_without_ext = os.path.splitext(fname)[0].replace("_", " ").replace("-", " ")
            name_embedding = embed(name_without_ext)
            content_embedding = embed(text[:2000])

            index[path] = {
                "snippet": text[:200],
                "name_embedding": name_embedding,
                "content_embedding": content_embedding,
            }
            indexed += 1

    if indexed == 0 and scanned > 0:
        reasons = []
        if skipped_extensions:
            reasons.append(
                f"{len(skipped_extensions)} file(s) had a non-matching extension "
                f"(saw: {sorted(skipped_extensions)}, looking for: {req.extensions})"
            )
        if empty_count:
            reasons.append(f"{empty_count} matching file(s) were empty (no text inside)")
        if unreadable_count:
            reasons.append(f"{unreadable_count} matching file(s) couldn't be read")
        reason_text = "; ".join(reasons) if reasons else "no readable text was found"
        return {
            "indexed_files": 0,
            "total_in_index": len(index),
            "warning": f"Found {scanned} file(s) in that folder, but indexed none. "
                       f"Reason: {reason_text}.",
        }
    if scanned == 0:
        return {
            "indexed_files": 0,
            "total_in_index": len(index),
            "warning": f"The folder '{req.folder_path}' exists but contains no files "
                       f"(checked subfolders too). Double check it's the right path.",
        }

    save_index(index)
    return {"indexed_files": indexed, "total_in_index": len(index)}


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


@app.get("/search")
def search(
    q: str = Query(..., description="Natural language question"),
    top_k: int = 5,
    mode: str = Query("both", description="'filename', 'content', or 'both'"),
):
    """Embed the query, rank every indexed file by cosine similarity."""
    index = load_index()
    if not index:
        return {"results": [], "message": "Index is empty — call POST /index first."}

    if mode not in ("filename", "content", "both"):
        return {"results": [], "error": f"Invalid mode '{mode}'. Use 'filename', 'content', or 'both'."}

    # Handle indexes built before the filename/content split existed.
    stale_entries = [p for p, d in index.items() if "name_embedding" not in d]
    if stale_entries:
        return {
            "results": [],
            "error": f"{len(stale_entries)} indexed file(s) were indexed with an older "
                     f"version of this app and need to be re-indexed before search will "
                     f"work. Click Index again on the same folder(s).",
        }

    query_embedding = embed(q)

    scored = []
    for path, data in index.items():
        name_score = cosine(query_embedding, data["name_embedding"])
        content_score = cosine(query_embedding, data["content_embedding"])

        if mode == "filename":
            combined = name_score
        elif mode == "content":
            combined = content_score
        else:  # both — a file counts as relevant if EITHER its name or its content is a strong match
            combined = max(name_score, content_score)

        scored.append((combined, name_score, content_score, path, data["snippet"]))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_results = scored[:top_k]

    response = {
        "results": [
            {
                "file": path,
                "score": round(combined, 4),
                "name_score": round(name_score, 4),
                "content_score": round(content_score, 4),
                "snippet": snippet,
            }
            for combined, name_score, content_score, path, snippet in top_results
        ],
        "mode": mode,
    }

    # A real semantic match is typically 0.3+. Below that, results are likely
    # noise rather than genuinely relevant — flag it instead of implying
    # confidence the ranking doesn't actually have.
    if top_results and top_results[0][0] < 0.3:
        response["note"] = (
            "Low confidence: none of your indexed files closely match this "
            "query in meaning. These are just the least-unrelated of what's "
            "indexed, not strong matches."
        )

    return response


@app.get("/status")
def status():
    index = load_index()
    return {"indexed_files": len(index), "model": MODEL_NAME}


def start():
    print("Starting local semantic search API on http://0.0.0.0:9120 ...")
    uvicorn.run(app, host="0.0.0.0", port=9120)


if __name__ == "__main__":
    start()
