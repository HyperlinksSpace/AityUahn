FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY python ./python
COPY config ./config

RUN pip install --no-cache-dir -e .

ENV PYTHON_CONFIG=/app/config/forge.example.yaml
ENV PYTHON_WORKSPACE_ROOT=/workspace

VOLUME ["/workspace", "/data"]
WORKDIR /data

ENTRYPOINT ["aityuahn"]
CMD ["--help"]
