FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# Copy requirements.txt first. Docker then caches the dependency layer between code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ffai ./ffai

CMD ["python", "-m", "ffai", "run"]
