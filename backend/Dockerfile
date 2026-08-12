FROM python:3.12-slim

# Prevent Python from writing pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /workspace

# Install system build dependencies required for compiling some Python modules
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY requirements.txt /workspace/
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Pre-download NLTK and spaCy models to bake them into the Docker image
RUN python -m nltk.downloader -d /usr/local/share/nltk_data punkt stopwords wordnet omw-1.4 vader_lexicon \
    && python -m spacy download en_core_web_sm

# Copy the rest of the application code
COPY . /workspace/

EXPOSE 8000
