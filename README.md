# Satellite Imagery-Based Property Valuation (Multimodal Regression)

This repo predicts house `price` using:
- Tabular features (bedrooms, sqft, lat/long, etc.)
- Satellite imagery fetched from coordinates

## 1) Setup

### Create environment
```bash
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows
pip install -U pip
pip install -r requirements.txt
