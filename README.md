# PDF Form Autofiller Agent

A lightweight, local Python tool that autofills flattened PDF forms using OCR and coordinate-based text overlay. It learns form layouts and saves them as templates for faster, deterministic reuse.

## Features
- **Local & Private**: Runs entirely on your machine. No data leaves your system.
- **Smart OCR**: Detects field labels (e.g., "Name:", "Date:") and calculates filling coordinates.
- **Template Memory**: Saves detected layouts. Subsequent runs on the same form skip OCR and use the saved template.
- **Non-Destructive**: Overlays text onto the existing PDF without altering original content.

## Prerequisites

### 1. System Dependencies
You need to install **Poppler** (for PDF-to-image conversion) and **Tesseract OCR** (for text detection).

**macOS (Homebrew):**
```bash
brew install poppler tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install poppler-utils tesseract-ocr
```

**Windows:**
- Download and install [Poppler](https://github.com/oschwartz10612/poppler-windows/releases/) (add `bin` to PATH).
- Download and install [Tesseract](https://github.com/UB-Mannheim/tesseract/wiki) (add to PATH).

### 2. Python Dependencies
Install the required Python packages:
```bash
pip install -r requirements.txt
```

## Usage

### 1. Prepare your Data
Create a JSON file (e.g., `data.json`) with the fields you want to fill. Keys should match the labels in the PDF (case-insensitive partial matching).

```json
{
  "Name": "John Doe",
  "Date": "2023-10-27",
  "Student ID": "12345678"
}
```

### 2. Run the Agent
```bash
python autofill.py input_form.pdf data.json
```

### 3. Output
- **Filled PDF**: Saved as `input_form_filled.pdf`.
- **Template**: Saved in `templates/` directory. Next time you run this form, it will use the template.

## How It Works
1. **Hash**: Calculates a unique hash of the PDF to check for existing templates.
2. **OCR (First Run)**: If no template exists, converts PDF pages to images and uses Tesseract to find text bounding boxes.
3. **Mapping**: Looks for labels matching your JSON keys. Calculates a "safe" writing zone to the right of the label.
4. **Fill**: Overlays text using PyMuPDF at the calculated or loaded coordinates.
5. **Save**: Stores the mapping in `templates/<hash>.json` for future use.
