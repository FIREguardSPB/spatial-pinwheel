FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy project definition from root (backend/)
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir .

# Copy source code
COPY . /app

EXPOSE 3000
CMD ["uvicorn", "apps.api.main:app", "--host", "0.0.0.0", "--port", "3000"]
