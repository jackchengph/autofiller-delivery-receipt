import fitz

def find_lines(pdf_path):
    doc = fitz.open(pdf_path)
    page = doc[0]
    pix = page.get_pixmap()
    
    width = pix.width
    height = pix.height
    
    print(f"Pixmap size: {width}x{height}")
    
    # helper to check if pixel is dark (black line)
    def is_dark(x, y):
        if x < 0 or x >= width or y < 0 or y >= height: return False
        r, g, b = pix.pixel(x, y)
        return (r + g + b) < 150  # Increased threshold for lighter gray lines
        
    # 1. Find Vertical Lines (Columns)
    # Scan multiple lines to catch the table
    scan_ys = [0.35, 0.40, 0.45] # 35%, 40%, 45% of height
    
    v_lines = []
    
    for pct in scan_ys:
        scan_y = int(pct * height)
        for x in range(width):
            if is_dark(x, scan_y):
                pdf_x = x * (page.rect.width / width)
                # Filter noise
                if not any(abs(pdf_x - v) < 5 for v in v_lines):
                    v_lines.append(pdf_x)
    v_lines.sort()
                
    print(f"Vertical Lines found at X: {v_lines}")
    
    # 2. Find Horizontal Lines (Rows)
    # Scan vertical line at X = ~100 (inside Description column)
    scan_x = int(100 * (width / page.rect.width))
    
    h_lines = []
    for y in range(height):
        if is_dark(scan_x, y):
            # Convert back to PDF points
            pdf_y = y * (page.rect.height / height)
            if not h_lines or abs(pdf_y - h_lines[-1]) > 5:
                h_lines.append(pdf_y)
                
    print(f"Horizontal Lines found at Y: {h_lines}")

find_lines("delivery_receipt_template.pdf")
