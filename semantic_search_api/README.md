# Local File Search

Search your own files by *meaning*, not just keyword matching — entirely on
your own machine, nothing uploaded anywhere.

## Install

```
pip install JCcoder0901semantic-search
```

## Run

```
python -m search_api.main
```

This works every time, regardless of how your terminal's PATH is set up —
no extra configuration needed.

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
initial run command.

First run downloads a small embedding model (~50MB via `fastembed`), needs
internet once, then works fully offline.

Your search index is saved to `~/.local_file_search/index.pkl` — in your own
user folder, separate from the installed package. It survives reinstalls
and updates, and it's private to your own machine; installing this package
never gives anyone else access to your indexed files or search history.

## Optional: using the `localsearch` shortcut command instead

`pip` also installs a shortcut command, `localsearch`, that does the exact
same thing as `python -m search_api.main`. Whether it works out of the box
depends on your system's PATH setup — a well-known Python packaging quirk,
most common on Windows, and not something wrong with your installation if it
doesn't. There's no need to fix this; `python -m search_api.main` above
always works regardless. If you'd like the shortcut working anyway:

```
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
```
Add the folder that prints to your system PATH (search "environment
variables" in the Start menu on Windows), then open a *new* terminal window.

Alternatively, [pipx](https://pipx.pypa.io) is built to handle this
automatically — though it can hit the same PATH issue itself on some
systems, in which case run `python -m pipx ensurepath` instead of
`pipx ensurepath`.

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

## Publishing new versions (for the maintainer)

This project publishes to PyPI automatically via GitHub Actions
(`.github/workflows/publish.yml`) using PyPI's Trusted Publishing — no
manual `twine upload` or API token needed.

To release a new version:
1. Bump `version` in `pyproject.toml`.
2. Commit and push the change.
3. On GitHub: **Releases → Draft a new release**, tag it (e.g. `v0.1.1`),
   and publish the release.

That triggers the workflow, which builds the package and uploads it to
PyPI automatically.
