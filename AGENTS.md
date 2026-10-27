# AGENTS.md

Guidance for coding agents working in this repository.

## What this repo is

The `plotting-service` is a FastAPI application that provides an
[h5grove](https://github.com/silx-kit/h5grove) implementation for serving and plotting scientific
data in the Flexible Interactive Automation (FIA) system — specifically NeXus/HDF5 files from
`/ceph`, IMAT image data from `/imat`, and live data streams. See `README.md` for environment
variables, local running instructions, and the expected reduced-data directory structure — read it
before making changes.

## Position in the FIA service

### Overarching FIA architecture

FIA is a multi-repository system (all checked out as siblings under the same parent workspace
directory) that automatically reduces instrument data, and also lets users browse, plot, and rerun
that data interactively:

```text
[ISIS Instrument Archive (/archive, /imat) & lastrun.txt]
        │
        ▼
  file-watcher (Kopf Operator + Per-Instrument Watcher Pods)
        │  publishes file path to RabbitMQ: `watched-files`
        ▼
  run-detection ◄──── fetches instrument rules (`GET /instrument/{inst}/specification`) ────► FIA-API
        │  ingests .nxs metadata, verifies rules, publishes JobRequest JSON
        │  to RabbitMQ: `scheduled-jobs` (or retries via `failed-watched-files`)
        ▼
  jobcontroller (job_creator) ◄──── requests PreScript (`GET /script/{inst}`) & posts Job ──► FIA-API ◄──► autoreduction-scripts
        │  spawns Kubernetes Job in cluster:
        ├──► Main container: runners (`ghcr.io/fiaisis/mantid` or `mantid-imaging`) -> writes reduced data to `/ceph`
        └──► Sidecar container: jobcontroller (job_watcher) -> updates job status/outputs in FIA-API (`PATCH /job/{id}`)

[Interactive / Web & Live Data Paths]
  scigateway (Host App) ──► frontend (FIA React Plugin)
                                ├──► fia-auth (UOWS login, JWT verify/refresh, `/experiments` RB lookup)
                                ├──► FIA-API (runs, jobs, scripts, specifications, reruns -> `watched-files` / `scheduled-jobs`)
                                └──► plotting-service (THIS REPO) (h5grove NeXus/HDF5 & IMAT image serving from `/ceph` & `/imat`)

  Kafka (`<INST>_events`, `<INST>_sampleEnv`, `<INST>_runInfo`)
        └──► live-data (Live Data Operator + Mantid Live Data Processor fetching `/live-data/{inst}/script` from FIA-API)

  LLSP (Long Lived Script Processors: `LLSP-API` + RabbitMQ + Celery `LLSP-Worker` built on `ghcr.io/fiaisis/mantid`)

[Infrastructure & Deployment]
  k8s (Terraform + Ansible for OpenStack clusters, Redpanda, local Minikube)
  gitops (ArgoCD App-of-Apps & Kustomize `base`/`envs`/`variants` manifests for all FIA services)
```

### This repository's location (upstream, downstream & siblings)

- **Role**: `plotting-service` is the data-serving backend for interactive visualization (H5Web
  NeXus/HDF5 viewers, text file previews, IMAT image stack viewing, and live-data plotting).
- **Upstream callers (who calls `plotting-service`)**:
  - `frontend` (`../frontend`) — the FIA React plugin (configured via `VITE_FIA_PLOTTING_API_URL` /
    `VITE_FIA_DATA_VIEWER_URL`) requests HDF5 metadata/slices (`h5grove` endpoints), text files,
    IMAT image slices/stacks, and live-data streams.
- **Downstream callees / data sources**:
  - `fia-auth` (`../fia-auth`) — called via `FIA_AUTH_URL` (authenticated with `FIA_AUTH_API_KEY`)
    to resolve user experiment (RB) permissions when validating JWT access to experiment files.
  - `/ceph` (`CEPH_DIR`) — reads reduced NeXus/HDF5 and text output files written by `runners`
    (`../runners`) jobs spawned by `jobcontroller` (`../jobcontroller`), as well as live-data output
    written by `live-data` (`../live-data`).
  - `/imat` (`IMAT_DIR`) — reads IMAT image files directly from the IMAT mount.
- **Sibling repositories to check when changing contracts**: `../frontend`
  (`src/lib/plottingServiceAPI.ts` and viewer components), `../fia-auth` (JWT claims and
  `/experiments` endpoint), `../live-data` (live data output paths), and `../gitops`
  (`components/plotting-service/` deployment manifests and env vars).

### Core technologies
- **Python**: version/minimum is defined by `requires-python` in `pyproject.toml` — do not hardcode a
  version here; always check `pyproject.toml` (and `.github/workflows/`, which may pin a newer CI
  version) before creating an environment.
- **FastAPI** + **uvicorn**: Web framework and ASGI server.
- **h5grove** (`h5grove[fastapi]`): Backend for HDF5/NeXus metadata and dataset slicing.
- **Pillow**: Image processing for IMAT image routes.
- **PyJWT** + **requests**: JWT validation and calls to `fia-auth`.
- **Pytest** (+ `pytest-cov`, `pytest-random-order`, `pytest-asyncio`): Testing framework.
- **Ruff**: Linting and formatting (`line-length = 120`, rules in `pyproject.toml`).
- **Mypy**: Static type checking (`mypy --strict plotting_service`).
- **Docker**: Containerization (`Dockerfile`).

---

## Repository structure

```
plotting_service/            Main application package — FastAPI entrypoint, JWT/API-key auth
                              middleware, custom exceptions, and safe path/file-lookup utilities at
                              top level
  routers/                   FastAPI routers: generic h5grove/file-finding/text retrieval, IMAT
                              image data routes, and live-data streaming routes
  services/                  Business logic (e.g. Pillow-based image processing for IMAT)

test/                        Pytest test suite — unit and API tests covering routes, auth, and path
                              utilities, plus test_ceph/ fixture data mimicking the reduced-data and
                              IMAT directory layout

Dockerfile                   Production container image definition
.github/workflows/           CI workflows: test.yml, formatting-and-linting.yml, build-push.yml, etc.
pyproject.toml               Single source of truth for package metadata, pinned dependencies, and
                              ruff/mypy/pytest configuration
```

---

## `pyproject.toml` — read this first

`pyproject.toml` is the single source of truth for dependencies, extras, and tool config. Read it
before adding dependencies, changing supported Python versions, or changing lint/type rules:

- Runtime dependencies and optional extras (`formatting`, `test`, `all`) are pinned with `==` — keep
  any new dependencies pinned the same way.
- `requires-python` defines the minimum supported Python version; check it and `.github/workflows/`
  before creating an environment.
- Ruff (`[tool.ruff]`, `[tool.ruff.lint]`) enforces `line-length = 120` and a comprehensive rule set
  (bandit `S`, bugbear `B`, pathlib `PTH`, type-checking imports `TCH`, FastAPI `FAST`, pylint `PL`,
  etc.). Check `[tool.ruff.lint.ignore]` before "fixing" intentionally ignored rules.
- CI runs `mypy --strict plotting_service`.

---

## Path handling & authentication conventions

### Environment variables & directory layout
The service relies on environment variables for data locations and auth (see `README.md`):
- `CEPH_DIR`: Base directory containing reduced data (default: `/ceph`).
  Expected layout for reduced experiment files:
  `<CEPH_DIR>/<instrument>/RBNumber/RB<RBNUMBER>/autoreduced/<NEXUS FILE>`
  (e.g. `/ceph/mari/RBNumber/RB12345/autoreduced/MAR_1231231.nxspe`).
- `IMAT_DIR`: Base directory for IMAT data (default: `/imat`).
- `DEV_MODE`: Set to `True` to bypass authentication in local development (default: `False`).
- `API_KEY`: API key required for internal endpoints (e.g. updating settings/cache keys).
- `JWT_SECRET`: Symmetric secret used for JWT verification (default: `shh`).
- `FIA_AUTH_URL` / `FIA_AUTH_API_KEY`: URL and API key for querying `fia-auth`.

Always use `pathlib.Path` (enforced by Ruff `PTH` rules) and preserve path-traversal checks in
`plotting_service/utils.py`. Note that `/ceph` and `/imat` are Linux container mounts and do not
necessarily exist on a developer machine; tests use `test/test_ceph` or temporary paths.

### Authentication middleware
`plotting_service` enforces JWT-based authentication and API key checks via `check_permissions` and
`check_live_permissions`. Keep these permission checks in mind whenever adding or modifying routes.

---

## Environment & running commands

Do not assume any particular machine already has a conda env, kubectl context, or virtualenv set up
— check what is available first. Prefer `conda` when available (`command -v conda` on Linux/macOS or
`where conda` on Windows); fall back to a Python `venv` only if conda is not installed.

1. Check existing conda environments:
   ```shell
   conda env list
   ```
   If a matching env exists (e.g. `plotting-service`), use it with
   `conda run -n <env-name> <command>` or `conda activate <env-name>`.
2. If no suitable conda env exists but `conda` is installed, create one using the Python version
   from `pyproject.toml` / `.github/workflows/`:
   ```shell
   conda create -n plotting-service python=<version-from-pyproject.toml-or-CI> -y
   conda run -n plotting-service pip install ".[all]"
   ```
3. Only if `conda` is not installed, fall back to a virtualenv:
   ```shell
   python3 -m venv .venv        # Linux/macOS (use `python` on Windows)
   . .venv/bin/activate         # POSIX shell (.venv\Scripts\Activate.ps1 on PowerShell)
   pip install ".[all]"
   ```

### Running the API & tests
- **Run development server**:
  ```shell
  conda run -n <env-name> uvicorn plotting_service.plotting_api:app --reload
  ```
- **Run tests, linting & type checking**:
  ```shell
  conda run -n <env-name> pytest test --random-order --random-order-bucket=global
  conda run -n <env-name> ruff check .
  conda run -n <env-name> ruff format --check .
  conda run -n <env-name> mypy --strict plotting_service
  ```

## Kubernetes commands

Available kubectl contexts vary per machine/operator — always run `kubectl config get-contexts`
first before targeting a cluster. Never rely on the current context; always pass `--context`
explicitly at the **end** of the command:

```shell
kubectl get pods -n fia --context <context-name>
kubectl logs deploy/plotting-service -n fia --context <context-name>
```

Double- and triple-check the context name before running anything against a production-like cluster.

## Managing issues

This repo has no local `.github/ISSUE_TEMPLATE/`; GitHub serves the org-wide default template from
`fiaisis/.github` instead. Always use it rather than inventing an ad hoc issue format:

```shell
gh issue create --template Issue
```

Check `gh issue list` / `gh issue view <number>` first to avoid duplicates.

## Branch naming

Branches use `snake_case` descriptions of the work being done. Do not use category prefixes like
`feature/` or `fix/`.

- **Format**: `description_of_work` (e.g. `live_data_path`, `update_agent_guidelines`).

## Commit messages

`main`'s history (`git log --oneline main`) is predominantly **squash merges**: one commit per PR,
titled `<PR title> (#<PR number>)`. This has two practical consequences:

- **The PR title is what actually survives into permanent history.** Individual commits on a working
  branch are squashed on merge, so getting the PR title right (see "Pull request process" below)
  matters more than crafting a commit-by-commit history.
- **Individual commit messages still matter for review and for the squash commit body.** By default,
  GitHub's squash merge concatenates every commit subject on the branch into the squashed commit's
  body. Write each commit as a focused, reviewable unit of work with a clear, imperative-mood
  summary line (and a short *why* body paragraph on non-trivial commits) — avoid noise like `wip` or
  `fix` that would leak into the squashed body. Leave auto-generated Dependabot commit messages as-is.

## Requirements for code changes

Only run tests, linters, and type checkers when they are **relevant to the files you actually
changed** — if a change only touches documentation (e.g. `.md` files), skip `pytest`, `ruff`, and
`mypy`. When you do change Python code, dependency manifests, or configuration, before considering
the change complete:
1. **Add or update unit tests** in `test/` for any new or changed behavior.
2. **Add or update E2E coverage** in `test/test_e2e.py` when the change affects an integration path
   that test already exercises.
3. **Run the linter and type checker** (`ruff check .`, `ruff format .`,
   `mypy --strict plotting_service`) and fix everything reported.
4. **Run the full test suite with coverage** and confirm coverage has not regressed. Note this repo
   does **not** upload coverage to Codecov in CI (`.github/workflows/test.yml` only produces a local
   `--cov-report=xml`), so compare the terminal summary (use `--cov-report=term-missing`) before and
   after your change yourself rather than relying on an external badge.

## Pull request process

1. **Local validation** before opening a PR (when `.py` / `pyproject.toml` / container files are
   changed; skip for `.md`-only changes):
   ```shell
   conda run -n <env-name> pytest test --random-order --random-order-bucket=global
   conda run -n <env-name> ruff check .
   conda run -n <env-name> ruff format .
   conda run -n <env-name> mypy --strict plotting_service
   ```
   Note: the CI workflow (`.github/workflows/formatting-and-linting.yml`) also runs `ruff format .`,
   `ruff check --fix .`, and `mypy --strict plotting_service` on every non-`main` push and
   auto-commits any fixes back to the branch as `"Formatting and linting commit"`.
2. **PR title**: a clear, concise description in normal grammar (e.g. `Update agent guidelines`). Do
   not use `snake_case` for PR titles.
3. **PR description**: use the org-wide default template from `fiaisis/.github`
   (`.github/pull_request_template.md` — no local override in this repo), which is just
   `Closes # <Issue Number>` followed by a `## Description` section. Ask the user for the issue
   number if one isn't evident from the task, or confirm there is none to link.
4. **AI-assistance label**: attach a label to the PR indicating that it was made with the assistance
   of AI. Check existing labels first with `gh label list` (e.g. `AI` or `AI_code` in this org) and
   apply the matching label via `gh pr create --label <label>` or
   `gh pr edit <number> --add-label <label>`; if the repo does not have an AI label yet, create one
   first (`gh label create "AI" --description "Created with the assistance of AI"`).

## Handling Dependabot PRs

Dependabot creates PRs grouped as `python-packages`, `action-packages`, and
`plotting-service-docker-image` per `.github/dependabot.yml`. When asked to handle these:

1. **List and identify**: `gh pr list` to find open Dependabot PRs.
2. **Review changes**: `gh pr diff <number>`, paying close attention to major version bumps in
   `pyproject.toml`, `Dockerfile`, or `.github/workflows/`.
3. **Validate**:
   - Python/dependency changes: `gh pr checkout <number>`, install updated dependencies
     (`pip install ".[all]"`), and run tests, ruff, and `mypy --strict plotting_service`.
   - Docker/Action changes: verify CI checks pass with `gh pr checks <number>`.
4. **Approve and merge** once validation passes:
   ```shell
   gh pr review <number> --approve
   gh pr merge <number> --merge
   ```
   Use `--admin` if blocked by branch protection (`gh pr merge <number> --merge --admin`).
5. **Clean up**: close redundant/superseded PRs with `gh pr close <number> --delete-branch`.
6. **Final verification**: checkout `main`, pull latest changes, and re-run `pytest` to confirm
   `main` is green.

## General working practices

- Prefer the `read` tool (with `offset`/`limit`) over `sed -n`, `cat`, or similar shell one-liners
  when inspecting file contents, and prefer the `write` and `edit` tools over `bash` (`cat <<EOF`,
  `sed -i`, `echo >`), Python one-liners, or other non-tool-based commands whenever creating or
  modifying files.
- Ask the user a clarifying question whenever a task is ambiguous (e.g. expected path structure on
  `/ceph` vs `/imat`, auth requirements for a route, or whether an issue number exists to link in a
  PR) rather than guessing.
- Keep dependency versions pinned with `==` in `pyproject.toml` consistent with the existing style.

## Keeping this document up to date

If a change you make would make any information in this `AGENTS.md` inaccurate or incomplete —
e.g. a new environment variable, a changed directory layout, a new/renamed CI workflow, an updated
Dependabot grouping, a new sibling-repo contract, or a different testing/linting command — update
the relevant section of this file as part of the same change. Treat it the same way you would treat
`README.md`: documentation that goes stale is worse than no documentation, so don't leave it to a
future agent or PR to notice the drift.
