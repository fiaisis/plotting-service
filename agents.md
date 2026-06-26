# AI Agents Documentation

This document provides guidance for AI agents (like Claude, Junie, etc.) working on the `plotting-service` repository.

## Project Overview

The `plotting-service` is a FastAPI application that provides a [h5-grove](https://github.com/silx-kit/h5grove) implementation for serving and plotting scientific data, specifically targeting NeXus/HDF5 files and IMAT image data.

### Core Technologies
- **FastAPI**: Web framework.
- **h5grove**: Backend for HDF5/NeXus data access.
- **Pillow**: Image processing (for IMAT data).
- **Pytest**: Testing framework.
- **Ruff**: Linting and formatting.

## Repository Structure

- `plotting_service/`: Main package.
    - `plotting_api.py`: Application entry point and middleware (authentication).
    - `routers/`: API route definitions.
        - `plotting.py`: Generic file finding and text retrieval.
        - `imat.py`: IMAT-specific image data routes.
        - `live_data.py`: Routes for handling live data streams.
    - `services/`: Business logic.
        - `image_service.py`: PIL-based image processing.
    - `utils.py`: Path manipulation and file searching logic.
- `test/`: Test suite.
- `pyproject.toml`: Project metadata and dependencies.
- `Dockerfile`: Containerization setup.

## Development Workflow

### Setup

The project aims to be agnostic regarding local developer setups.

#### Using Conda (Recommended if available)
If you use conda, check if the `plotting-service` environment exists. If not, create it and install dependencies:

```bash
# Check if conda is installed
which conda

# Check if environment exists
conda env list | grep plotting-service

# If it doesn't exist, create it (Python 3.11+)
conda create -n plotting-service "python>=3.11" -y

# Activate and install dependencies
conda activate plotting-service
pip install .[all,test,formatting]
```

#### Using Pip/Venv (Fallback if conda is not available)
If conda is not installed or you prefer standard virtual environments:

```bash
python -m venv venv
source venv/bin/activate
pip install .[all,test,formatting]
```

### Running the API (Development)
```bash
uvicorn plotting_service.plotting_api:app --reload
```

### Running Tests
```bash
pytest
```

### Branch Naming

Branches should use snake_case descriptions of the work being done. Do not use category prefixes (like `feature/` or `fix/`).

- **Format**: `description_of_work` (e.g., `update_agent_guidelines`).

### Creating Issues

To ensure issues are consistent and contain necessary context, use the repository's issue template. You can fetch and use the latest template directly via the GitHub CLI:

```bash
gh issue create --template Issue
```

Filling this in will provide the correct template for Features or Bugs as appropriate.

### Pull Request Process

1. **Local Validation**: Before opening a PR, ensure all tests pass and code quality checks are green.
   ```bash
   pytest
   ruff check .
   mypy plotting_service
   ```
2. **PR Description**: Use the "## Description" header followed by a clear explanation of your changes.
3. **Reference Issues**: Link any related issues in the description (e.g., "Closes #123").

### Handling Dependabot PRs

Dependabot periodically creates pull requests to update dependencies and GitHub Actions. Agents should follow this workflow:

1. **List and Identify**: Use `gh pr list` to find open Dependabot PRs.
2. **Review Changes**: Inspect the changes with `gh pr diff <number>`. Pay close attention to major version bumps in `pyproject.toml` or changes in `.github/workflows/`.
3. **Validation**:
    - **Python/Dependency changes**: If `pyproject.toml` or Python files are modified, perform local validation:
        - Checkout the PR branch: `gh pr checkout <number>`.
        - Run the full test suite: `pytest`.
        - Run linting and type checking: `ruff check .` and `mypy plotting_service`.
    - **GitHub Actions changes**: If `.github/workflows/` are modified, check that the actions have passed as part of the PR:
        - `gh pr checks <number>`
4. **Approve and Merge**:
    - If validation passes, approve the PR: `gh pr review <number> --approve`.
    - Merge the PR: `gh pr merge <number> --merge`.
    - **Note**: Use the `--admin` flag if the merge is blocked by branch protection policies (e.g., `gh pr merge <number> --merge --admin`).
5. **Clean up**: Close redundant or superseded PRs using `gh pr close <number> --delete-branch`.
6. **Final Verification**: After merging, return to the `main` branch, pull the latest changes, and run `pytest` one last time to ensure everything is correct.

### Agent Guidelines

#### Environment Setup
Agents should prefer using a conda environment named `plotting-service` if conda is available on the system PATH. 

If conda is not available, the agent should fallback to using a standard Python virtual environment (`venv`).

If an environment does not exist, the agent should offer to create it and install requirements from `pyproject.toml`.

### Path Handling
The service heavily relies on environment variables for data locations:
- `CEPH_DIR`: Base directory for reduced data (e.g., `/ceph`).
- `IMAT_DIR`: Base directory for IMAT data (e.g., `/imat`).

When working with file paths, use `pathlib.Path` and ensure compatibility with the directory structures expected by `utils.py`.

### Authentication
The API implements JWT-based authentication and API key checks in `plotting_api.py`. Be aware of `check_permissions` and `check_live_permissions` middleware when adding or modifying routes.

### Testing
- Always include/update tests in the `test/` directory.
- Use the existing test structure (e.g., `test_plotting_api.py`) as a template.
- Test data is often mocked or provided in `test/test_ceph`.

### Formatting
The project uses `Ruff` for linting and formatting. Ensure your changes comply with the rules defined in `pyproject.toml`.
