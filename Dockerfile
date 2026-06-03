# Multi-stage build keeps the runtime image lean.
FROM python:3.11-slim AS builder
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir --prefix=/install ".[api,ui]"

FROM python:3.11-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY src/ src/
COPY data/ data/
ENV PYTHONPATH=/app/src
EXPOSE 8501
CMD ["streamlit", "run", "src/dealscreener/ui/app.py", \
     "--server.port=8501", "--server.address=0.0.0.0"]
