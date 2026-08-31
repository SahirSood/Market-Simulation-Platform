FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-runtime.txt .
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements-runtime.txt

COPY engine ./engine
RUN cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build engine/build --config Release

FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH=/opt/venv/bin:$PATH
ENV PYTHONPATH=/app/simulator:/app/engine/build:/app/engine/build/Release

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --from=builder /app/engine/build ./engine/build

COPY api ./api
COPY simulator ./simulator
COPY migrations ./migrations
COPY data ./data
COPY alembic.ini ./alembic.ini
COPY scripts ./scripts
RUN python scripts/container_smoke.py --require-native

EXPOSE 8000

CMD ["sh", "-c", "exec python -m uvicorn api.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
