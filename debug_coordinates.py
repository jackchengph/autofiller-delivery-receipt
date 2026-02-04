import fitz

def create_coordinate_map(template_path, output_path):
    doc = fitz.open(template_path)
    page = doc[0]
    
    red = fitz.pdfcolor["red"]
    blue = fitz.pdfcolor["blue"]
    
    # Draw horizontal lines every 50 points
    for y in range(0, int(page.rect.height), 20):
        page.draw_line(fitz.Point(0, y), fitz.Point(page.rect.width, y), color=blue, width=0.5)
        page.insert_text(fitz.Point(5, y), str(y), fontsize=6, color=blue)
        
    # Draw vertical lines every 50 points
    for x in range(0, int(page.rect.width), 50):
        page.draw_line(fitz.Point(x, 0), fitz.Point(x, page.rect.height), color=red, width=0.5)
        page.insert_text(fitz.Point(x, 10), str(x), fontsize=6, color=red)

    doc.save(output_path)
    print(f"Map saved to {output_path}")

create_coordinate_map('delivery_receipt_template.pdf', 'coordinate_map.pdf')
