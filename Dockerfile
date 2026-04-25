FROM python:3.11-slim

WORKDIR /app
ENV PORT=8080

# Install Node.js for google-play-scraper
RUN apt-get update && apt-get install -y nodejs npm && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN python -m spacy download en_core_web_sm

# Install Node deps
COPY package.json .
RUN npm install

# Copy project
COPY . .

# Create data directories
RUN mkdir -p data/raw data/processed data/archive

EXPOSE 8080

# Default: run dashboard
CMD ["python", "dashboard/app.py"]
