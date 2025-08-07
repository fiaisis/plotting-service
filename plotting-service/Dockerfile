FROM python:3.13.6-slim

WORKDIR /plotting-service

# Install fia_api to the container
COPY . /plotting-service
RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir .

CMD ["uvicorn", "plotting_service.plotting_api:app", "--host", "0.0.0.0", "--port", "80"]