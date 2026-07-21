FROM python:3.14-slim AS base

WORKDIR /plotting-service

COPY pyproject.toml README.md LICENSE ./
COPY plotting_service ./plotting_service

RUN python -m pip install --upgrade pip

FROM base AS test

RUN python -m pip install --no-cache-dir .[test]

COPY test ./test

FROM base AS runtime

RUN python -m pip install --no-cache-dir .

CMD ["uvicorn", "plotting_service.plotting_api:app", "--host", "0.0.0.0", "--port", "80"]
