FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
COPY . .
CMD ["uvicorn", "tube_manager.api:api", "--host", "0.0.0.0", "--port", "8000"]
