# ── Build stage ───────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL maintainer="LexRAG"
LABEL description="LexRAG — AI Service (FastAPI)"

# Install Tesseract OCR and system deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgomp1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN addgroup --system lexrag && adduser --system --ingroup lexrag lexrag

WORKDIR /app

COPY --from=builder /root/.local /home/lexrag/.local
COPY . .

RUN mkdir -p /app/uploads && chown -R lexrag:lexrag /app

USER lexrag

ENV PATH=/home/lexrag/.local/bin:$PATH
ENV PYTHONPATH=/app:/home/lexrag/.local/lib/python3.11/site-packages
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

EXPOSE 8001

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "2"]
