FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY . .

# Editable install, because the bundled data (data/l1_export) is found relative to the source tree
RUN pip install -e .

# Build the database from the bundled export now, so that the first request does not wait for it
RUN python -m codex.data.local_data_loader

# FLASK_SECRET_KEY is optional. Hosts such as Render provide the port in PORT.
CMD ["sh", "-c", "exec gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 codex.main:codex"]
