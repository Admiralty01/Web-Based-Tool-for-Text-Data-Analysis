FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements_mock.txt .
RUN pip install --no-cache-dir -r requirements_mock.txt

# Copy application files
COPY . .

# Expose port
EXPOSE 8000

# Start mock server
CMD ["python", "run_mocked_server.py"]
