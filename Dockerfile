FROM python:3.12-slim

WORKDIR /fia_api

# Install fia_api to the container
COPY . /fia_api
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

CMD ["uvicorn", "plotting_service.api:app", "--host", "0.0.0.0", "--port", "80"]