#!/bin/bash

echo "🤖 Setting up Intelligent Agent Wrapper..."

if command -v python3 &> /dev/null; then
    python_version=$(python3 -c "import sys; print('.'.join(map(str, sys.version_info[:2])))")
    if python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 7) else 1)"; then
        echo "[SUCCESS] Python $python_version found"
    else
        echo "[ERROR] Python 3.7+ required. Found Python $python_version"
        exit 1
    fi
else
    echo "[ERROR] Python 3 not found. Please install Python 3.7 or higher."
    exit 1
fi

if [ ! -d "venv" ]; then
    python3 -m venv venv
    echo "[SUCCESS] Virtual environment created"
fi

source venv/bin/activate || { echo "[ERROR] Failed to activate virtual environment"; exit 1; }
echo "[SUCCESS] Virtual environment activated"

pip install --upgrade pip
pip install -r requirements.txt
mkdir -p logs temp

if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "Please edit .env file with your API keys"
fi

python3 -c "
import nltk
try:
    nltk.download('punkt', quiet=True)
    nltk.download('stopwords', quiet=True)
    print('NLTK data downloaded')
except Exception as e:
    print(f'NLTK download warning: {e}')
"

if [ ! -f "credentials.json" ]; then
    echo "credentials.json not found. Please provide it from Google Cloud Console."
fi

echo "[SUCCESS] Setup completed! Run: streamlit run app.py"
