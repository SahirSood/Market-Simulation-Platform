FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app/simulator:/app/engine/build:/app/engine/build/Release

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential cmake git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY engine ./engine
RUN cmake -S engine -B engine/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build engine/build --config Release

COPY api ./api
COPY simulator ./simulator

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.server:app", "--host", "0.0.0.0", "--port", "8000"]
