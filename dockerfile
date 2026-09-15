# =====================================================
# STAGE 1: Builder (Handles dependency installation)
# Using python:3.13-slim if available
# =====================================================
FROM python:3.13-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1. Copy requirements file
COPY requirements.txt .

# Mandatory step to install all dependencies efficiently.
RUN pip install --upgrade pip && \
    pip install -r requirements.txt --no-cache-dir

# =====================================================
# STAGE 2: Runtime (Minimal image for execution)
# =====================================================
FROM python:3.13-slim AS runner

WORKDIR /app

# Copy ONLY the installed packages from the builder stage to keep the image small.
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy all remaining source code
COPY . .

# Define the entry point script that runs your main assistant logic
ENTRYPOINT ["python", "main.py"]