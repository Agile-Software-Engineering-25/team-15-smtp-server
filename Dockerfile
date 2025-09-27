# Dockerfile
FROM python:3.11-slim

# Faster installs & smaller image
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# Add a non-root user
RUN useradd -ms /bin/bash app

# Install aiosmtpd (do NOT pin to 1.4.6)
RUN pip install aiosmtpd

# Copy code
WORKDIR /app
COPY app.py /app/app.py

# Default env (can override in K8s)
ENV LISTEN_HOST=0.0.0.0 LISTEN_PORT=2525 OVERRIDE_HEADER_FROM=true

USER app
EXPOSE 2525
CMD ["python", "-u", "/app/app.py"]
