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

# install torch and flash-attention
pip install torch==2.3.0 torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
pip install wheel
pip install flash-attn --no-build-isolation

# Install secondary dependencies
pip install -r requirements.txt
