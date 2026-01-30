import os
import sys
import json
import hashlib
import argparse
import logging
from typing import Dict, Optional, List, Tuple

# Third-party libraries
import fitz  # PyMuPDF
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

TEMPLATE_DIR = "ocr_cache"

class FormAutofiller:
    def __init__(self, pdf_path: str, data: Dict[str, str]):
        self.pdf_path = os.path.abspath(pdf_path)
        self.data = data
        self.doc = fitz.open(self.pdf_path)
        self.pdf_hash = self._get_pdf_hash()
        self.template_path = os.path.join(TEMPLATE_DIR, f"{self.pdf_hash}.json")
        
        # Ensure template directory exists
        os.makedirs(TEMPLATE_DIR, exist_ok=True)

    def _get_pdf_hash(self) -> str:
        """Generates a SHA256 hash of the PDF file content."""
        hasher = hashlib.sha256()
        with open(self.pdf_path, 'rb') as f:
            buf = f.read()
            hasher.update(buf)
        return hasher.hexdigest()

    def _load_template(self) -> Optional[Dict]:
        """Loads an existing template if available."""
        if os.path.exists(self.template_path):
            try:
                with open(self.template_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load template: {e}")
        return None

    def _save_template(self, field_map: Dict):
        """Saves the detected field coordinates to a JSON file."""
        try:
            with open(self.template_path, 'w') as f:
                json.dump(field_map, f, indent=2)
            logger.info(f"Template saved to {self.template_path}")
        except Exception as e:
            logger.error(f"Failed to save template: {e}")

    def _normalize_text(self, text: str) -> str:
        """Normalizes text for comparison (lowercase, strip)."""
        return text.lower().strip().replace(":", "")

    def _find_coordinates(self) -> Dict:
        """
        Runs OCR on the PDF to find coordinates for the keys in self.data.
        Returns a nested dict: { page_num: { field_key: {x, y, fontsize} } }
        """
        logger.info("No template found. Running OCR to detect fields...")
        field_map = {}
        
        try:
            images = convert_from_path(self.pdf_path, dpi=200)
        except Exception as e:
            logger.error(f"Error converting PDF to images: {e}")
            sys.exit(1)

        for page_num, img in enumerate(images):
            page_map = {}
            pdf_page = self.doc[page_num]
            page_width_pt = pdf_page.rect.width
            page_height_pt = pdf_page.rect.height
            
            scale_x = page_width_pt / img.width
            scale_y = page_height_pt / img.height

            # Get detailed data
            ocr_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            n_boxes = len(ocr_data['text'])
            
            # Group words into lines using (block, par, line)
            lines = []
            current_line_words = []
            # key is (block_num, par_num, line_num)
            current_line_key = None
            
            for i in range(n_boxes):
                text = ocr_data['text'][i].strip()
                if not text:
                    continue
                
                # Create a unique key for the line
                line_key = (
                    ocr_data['block_num'][i],
                    ocr_data['par_num'][i],
                    ocr_data['line_num'][i]
                )
                
                x, y, w, h = ocr_data['left'][i], ocr_data['top'][i], ocr_data['width'][i], ocr_data['height'][i]
                
                if line_key != current_line_key:
                    if current_line_words:
                        lines.append(current_line_words)
                    current_line_words = []
                    current_line_key = line_key
                
                current_line_words.append({
                    'text': text,
                    'left': x, 'top': y, 'width': w, 'height': h
                })
            
            if current_line_words:
                lines.append(current_line_words)

            # Debug: Print all lines
            logger.info(f"--- Page {page_num + 1} OCR Lines ---")
            for line in lines:
                line_text = " ".join([w['text'] for w in line])
                logger.info(f"Line: '{line_text}'")

            # Find matches
            for key in self.data.keys():
                normalized_key = self._normalize_text(key)
                best_match = None
                
                for line in lines:
                    # Check if any word in the line matches the key start
                    # We want to find "Name:" or "Name"
                    
                    # Reconstruct line text for context
                    line_text = " ".join([w['text'] for w in line])
                    normalized_line = self._normalize_text(line_text)
                    
                    # Strict check: Line must start with the key
                    if not normalized_line.startswith(normalized_key):
                        continue

                    # Now find the specific word that ends the label
                    # e.g. "Name:" -> we want the right edge of this word
                    
                    temp_str = ""
                    for word in line:
                        # Accumulate text to handle split words if necessary
                        # But usually "Name:" is one or two words
                        word_clean = word['text'].lower().replace(":", "")
                        temp_str += word_clean
                        
                        # Check if we have matched the key
                        if normalized_key in temp_str:
                            # This is the word (or the last word of the label)
                            # We use its right edge
                            label_end_x = word['left'] + word['width']
                            label_top = word['top']
                            label_height = word['height']
                            
                            best_match = (label_end_x, label_top, label_height)
                            logger.info(f"MATCHED '{key}' at word '{word['text']}' in line '{line_text}'")
                            break
                    
                    if best_match:
                        break
                
                if best_match:
                    px, py, ph = best_match
                    # Convert to PDF coordinates
                    # Add padding (10pt) to start writing in the blank
                    pdf_x = (px * scale_x) + 10 
                    # Adjust Y to align with baseline (approximate)
                    # OCR 'top' is the top of the bbox. PDF text placement is usually baseline.
                    # Adding height is a good approximation for baseline.
                    pdf_y = (py * scale_y) + (ph * scale_y * 0.8)
                    
                    page_map[key] = {
                        "x": pdf_x,
                        "y": pdf_y,
                        "fontsize": 12
                    }
                else:
                    logger.warning(f"Could not find label for '{key}' on page {page_num+1}")

            if page_map:
                field_map[str(page_num)] = page_map

        return field_map

    def run(self):
        """Main execution method."""
        # 1. Check for template
        field_map = self._load_template()
        
        if not field_map:
            # 2. Run OCR if no template
            field_map = self._find_coordinates()
            if field_map:
                self._save_template(field_map)
            else:
                logger.error("No fields found via OCR. Cannot proceed.")
                return

        # 3. Fill PDF
        filled_count = 0
        skipped_count = 0
        
        for page_num_str, fields in field_map.items():
            page_num = int(page_num_str)
            if page_num >= len(self.doc):
                continue
                
            page = self.doc[page_num]
            
            for key, coords in fields.items():
                if key in self.data:
                    value = self.data[key]
                    try:
                        # Insert text
                        page.insert_text(
                            (coords['x'], coords['y']),
                            str(value),
                            fontsize=coords.get('fontsize', 11),
                            color=(0, 0, 1) # Blue color to distinguish filled text
                        )
                        filled_count += 1
                    except Exception as e:
                        logger.error(f"Error filling '{key}': {e}")
                        skipped_count += 1
                else:
                    skipped_count += 1

        # 4. Save Output
        output_path = self.pdf_path.replace(".pdf", "_filled.pdf")
        self.doc.save(output_path)
        logger.info(f"Done! Filled {filled_count} fields. Output saved to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Autofill flattened PDF forms.")
    parser.add_argument("pdf_file", help="Path to the input PDF file")
    parser.add_argument("data_file", help="Path to the JSON data file")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pdf_file):
        print(f"Error: PDF file '{args.pdf_file}' not found.")
        sys.exit(1)
        
    if not os.path.exists(args.data_file):
        print(f"Error: Data file '{args.data_file}' not found.")
        sys.exit(1)
        
    try:
        with open(args.data_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        print("Error: Invalid JSON in data file.")
        sys.exit(1)

    agent = FormAutofiller(args.pdf_file, data)
    agent.run()

if __name__ == "__main__":
    main()
