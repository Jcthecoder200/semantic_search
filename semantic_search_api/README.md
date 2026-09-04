# Local File Search

Search your own files by *meaning*, not just keyword matching — entirely on
your own machine, nothing uploaded anywhere.

## Install

**Recommended: [pipx](https://pipx.pypa.io)** — installs the command and
automatically makes it available in your terminal, avoiding a common
Windows/Mac/Linux gotcha where plain `pip install` puts the command
somewhere your terminal doesn't look (see Troubleshooting below if you hit
this).

```
pip install pipx
pipx ensurepath
pipx install JCcoder0901semantic_search
```
*(rename `JCcoder0901semantic_search` once you've picked and published under your
chosen name)*

**Alternative: plain pip**
```
pip install JCcoder0901semantic_search
```

## Run

```
localsearch
```

If that command isn't found, see **Troubleshooting** below — this is a very
common first-run snag with Python command-line tools in general, not
specific to this one, and there's a guaranteed-to-work fallback.

Then open your browser to:
```
http://127.0.0.1:9120
```

You'll see a simple page:

1. **Index a folder** — type the full path to a folder you want searchable
   (e.g. `C:\Users\you\Documents\notes`), pick which extensions to include if
   you want more than the `.txt`/`.md` defaults, click **Index**.

2. **Search** — pick a mode (file name + content, file name only, or content
   only), type a plain-English question, click **Search**. Results are
   ranked by how close their *meaning* is to your question, not exact word
   matches — a file can show up even without containing your exact search
   terms.

That's the whole workflow — no curl, no JSON, no terminal commands after the
initial `localsearch`.

First run downloads a small embedding model (~50MB via `fastembed`), needs
internet once, then works fully offline.

Your search index is saved to `~/.local_file_search/index.pkl`, so it
survives restarts — you don't need to re-index folders you already indexed.

## Troubleshooting: "localsearch is not recognized"

This happens when `pip` (not `pipx`) installs the command into a folder your
terminal's PATH doesn't include — it's a well-known Python packaging quirk,
most common on Windows, and not something wrong with your installation.

**Guaranteed fix, works every time regardless of PATH:**
```
python -m search_api.main
```

**Permanent fix:** switch to `pipx` (see Install above) — it's built
specifically to solve this, or manually add Python's Scripts folder to your
PATH:
```
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```
Add the folder that prints to your system PATH (search "environment
variables" in the Start menu on Windows), then open a *new* terminal window.

## Running via Docker instead (optional)

If you'd rather not install anything into your system Python, a `Dockerfile`
is included.

```powershell
docker build -t local-file-search .
docker run -p 9120:9120 -v "${PWD}/data:/data" -v "${env:USERPROFILE}:/host" local-file-search
```
`${env:USERPROFILE}` mounts your whole Windows user folder as `/host` inside
the container, so a folder like `Documents\notes` in your profile becomes
`/host/Documents/notes` when typed into the app. `${PWD}/data:/data`
persists the index outside the container so it survives restarts.

## Notes on scope

- Only files you explicitly `Index` get searched — nothing is scanned
  automatically just because it exists on disk.
- Point Index at specific folders rather than an entire drive — indexing
  everything would be slow and pull in a lot of irrelevant files.
- Supported file types by default: `.txt` and `.md`. Add more via the
  `extensions` field in the Index request, or by editing
  `search_api/main.py`.

## How it works, briefly

- **Index**: for each matching file, embeds the filename and the content as
  two *separate* vectors (lists of numbers capturing meaning) using a small
  local model (via `fastembed`, no PyTorch/GPU required), and saves them to
  `index.pkl`.
- **Search**: embeds your question the same way, compares it against the
  stored vectors by cosine similarity, and returns the closest matches. The
  mode selector controls whether "closest" is judged by filename, content,
  or whichever of the two is the stronger match.

## Publishing this yourself (for the maintainer)

```
pip install build twine
python -m build
twine upload dist/*
```
Before your first upload: pick a unique name at pypi.org, update it in
`pyproject.toml` (`name` and the `localsearch` install command above), fill
in your name in `pyproject.toml` and `LICENSE`, and set up a PyPI API token
for `twine` to use.
