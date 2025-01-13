FROM python:3.9-alpine

# Install required packages
RUN apk add --no-cache \
    rclone \
    curl \
    fuse \
    tzdata \
    bash \
    gcc \
    musl-dev \
    python3-dev \
    libffi-dev

# Install Python packages
RUN pip install fastapi uvicorn aiofiles requests python-multipart python-jose[cryptography] passlib[bcrypt]

# Create app directory and config
WORKDIR /app
RUN mkdir -p /config/rclone /data /mnt

# Copy application files
COPY main.py /app/
COPY entrypoint.sh /app/
RUN chmod +x /app/entrypoint.sh

# Environment variables
ENV RCLONE_CONFIG_URL=""
ENV AUTH_USERNAME=""
ENV AUTH_PASSWORD=""
ENV TZ="UTC"

# Expose port
EXPOSE 5572

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
