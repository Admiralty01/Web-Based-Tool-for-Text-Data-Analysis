FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements_mock.txt .
RUN pip install --no-cache-dir -r requirements_mock.txt \
    && python -m spacy download en_core_web_sm

# Copy application files
COPY . .

# Expose port
EXPOSE 8000

# Start app server
CMD ["python", "app_server.py"]
