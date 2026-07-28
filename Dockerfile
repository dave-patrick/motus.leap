FROM python:3.11-slim
WORKDIR /app
COPY reqs.txt .
RUN pip install --no-cache-dir -r reqs.txt
COPY . .
# Run as non-root
RUN useradd -m appuser
USER appuser
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
