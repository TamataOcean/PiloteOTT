FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    supervisor \
    && rm -rf /var/lib/apt/lists/*

# Create working directory
WORKDIR /app

# Copy project files (relative to context defined in docker-compose)
COPY systools /app/systools
COPY deploy/supervisord.conf /etc/supervisord.conf

# Install Python dependencies
COPY systools/config/config_PilotOTT.json /app/systools/config/config_PilotOTT.json
COPY systools/tides/marees.json /app/systools/tides/marees.json

RUN pip install --no-cache-dir paho-mqtt requests

# Command to run Supervisor
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisord.conf"]
