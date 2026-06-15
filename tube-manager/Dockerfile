FROM python:3.11-slim
WORKDIR /app
COPY reqs.txt .
RUN pip install --no-cache-dir -r reqs.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
