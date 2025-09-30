# Server image: minimal Flask + Gunicorn
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

#added for end of phase update/Sandra

RUN apt-get update \
&& apt-get install -y --no-install-recommends git ca-certificates openssh-client \ 
&& rm -rf /var/lib/apt/lists/*

# Copy project description, to instal dependencies
COPY pyproject.toml /app/pyproject.toml

# Install runtime dependencies
RUN pip install --no-cache-dir -e .

# Copy sources after dependencies installation
COPY src /app/src
COPY flag /app/flag
RUN pip install --no-cache-dir -e .

EXPOSE 5000

#added for end of phase one /Sandra
RUN apt-get update \
 && apt-get install -y --no-install-recommends gnupg \
 && rm -rf /var/lib/apt/lists/*

#added this for my watermark nr2
RUN apt-get update && apt-get install -y qpdf && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pikepdf


# Default command runs the web server
CMD ["gunicorn", "-b", "0.0.0.0:5000", "server:app"]

