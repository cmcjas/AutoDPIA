sudo apt install -y python3-pip

# Activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

sudo apt install npm
sudo apt install sqlite3
sudo apt install poppler-utils
sudo apt install tesseract-ocr
sudo apt install python3-poetry
sudo apt install libreoffice

# Install secondary dependencies
pip install -r requirements.txt

# Start the Flask application
python myapp.py