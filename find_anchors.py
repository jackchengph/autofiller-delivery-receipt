import fitz
import pytesseract
from PIL import Image
import io

def find_anchors(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    
    # Render page to image at high DPI for OCR
    pix = page.get_pixmap(dpi=150)
    img_data = pix.tobytes("png")
    img = Image.open(io.BytesIO(img_data))
    
    # Use pytesseract to get text data with bounding boxes
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    
    anchors = {}
    target_words = ["Date:", "Consignee:", "Location:", "Item", "Description"]
    
    n_boxes = len(data['text'])
    for i in range(n_boxes):
        text = data['text'][i].strip()
        if any(w in text for w in target_words):
            x, y, w, h = data['left'][i], data['top'][i], data['width'][i], data['height'][i]
            # Convert pixel coordinates back to PDF point coordinates
            # PDF is 72 DPI, Image is 150 DPI. Scale factor = 72/150 = 0.48
            scale = 72/150
            pdf_rect = fitz.Rect(x*scale, y*scale, (x+w)*scale, (y+h)*scale)
            print(f"Found '{text}' at {pdf_rect}")
            anchors[text] = pdf_rect

find_anchors("delivery_receipt_template.pdf")
