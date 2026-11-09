FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    SAATHI_DB_PATH=/data/saathi.db

WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock \
    && groupadd --gid 10001 saathi \
    && useradd --uid 10001 --gid saathi --no-create-home saathi \
    && mkdir /data && chown saathi:saathi /data
COPY --chown=saathi:saathi app.py gnani.py logic.py demo_security.py serve.py ./
COPY --chown=saathi:saathi static/ ./static/
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.getenv('PORT', '8000') + '/api/health', timeout=3)"
CMD ["python", "serve.py"]
