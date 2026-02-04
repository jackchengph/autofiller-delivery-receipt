import os
import sys
import logging
from datetime import datetime
from flask import Flask, render_template_string, request, send_file, flash, redirect, url_for, Response
import fitz  # PyMuPDF
import tempfile
import base64

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'supersecretkey-vercel-deployment'

# Get the base directory (parent of api folder)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ============ Delivery Receipt Filler Logic ============

TABLE_ROWS = [
    {'y_start': 275, 'y_end': 309},  # Row 1
    {'y_start': 309, 'y_end': 343},  # Row 2
    {'y_start': 343, 'y_end': 377},  # Row 3
    {'y_start': 377, 'y_end': 411},  # Row 4
    {'y_start': 411, 'y_end': 445},  # Row 5
]

TABLE_COLUMNS = {
    'item_description': {'x_start': 45, 'x_end': 325},
    'quantity': {'x_start': 335, 'x_end': 425},
    'remarks': {'x_start': 435, 'x_end': 615}
}


def fill_delivery_receipt(data, template_path):
    """Fill the PDF template with the provided data and return bytes."""
    
    doc = fitz.open(template_path)
    page = doc[0]
    
    white = fitz.pdfcolor["white"]
    black = fitz.pdfcolor["black"]
    # Font settings
    font_name = "helv"  # Helvetica
    base_font_size = 10
    font = fitz.Font(font_name)
    
    def draw_text_in_rect(rect, text, align="left", font_size=14, inset=0):
        """Draw text in a rectangle with auto-scaling and alignment.
        inset: padding for the whiteout box to preserve borders (x, y) or single int"""
        
        # Handle inset
        if isinstance(inset, int):
            inset_x, inset_y = inset, inset
        else:
            inset_x, inset_y = inset
            
        # 1. Clear the area (DISABLED for clean template to preserve grid lines)
        # We only need to write text now since the template is blank.
        # If we needed to erase, we would uncomment this:
        # shape = page.new_shape()
        # shape.draw_rect(erase_rect)
        # shape.finish(fill=white, color=white)
        # shape.commit()
        
        if not text:
            return

        # 2. Auto-scale font size
        current_font_size = font_size
        text_width = font.text_length(text, fontsize=current_font_size)
        rect_width = rect.width - 4  # 2px padding on each side
        
        while text_width > rect_width and current_font_size > 6:
            current_font_size -= 0.5
            text_width = font.text_length(text, fontsize=current_font_size)
            
        # 3. Calculate alignment
        # Vertical center baseline approximation: y_mid + font_size * 0.35
        # Lift text up larger amount for larger font (-8)
        y_pos = rect.y1 - ((rect.height - current_font_size) / 2) - 8
        
        if align == "center":
            x_pos = rect.x0 + (rect.width - text_width) / 2
        else:  # left
            x_pos = rect.x0 + 2  # Left padding
            
        text_point = fitz.Point(x_pos, y_pos)
        page.insert_text(text_point, text, fontname=font_name, fontsize=current_font_size, color=black)
    
    # Fill fields
    # Date (Top) - Anchor Y ~76
    date_rect = fitz.Rect(80, 76, 250, 92)
    draw_text_in_rect(date_rect, data['date'], font_size=16)
    
    # Consignee - Anchor Y ~160
    consignee_rect = fitz.Rect(115, 163, 400, 183)
    draw_text_in_rect(consignee_rect, data['consignee'], font_size=16)
    
    # Delivery Location - Anchor Y ~179
    location_rect = fitz.Rect(155, 182, 540, 198)
    draw_text_in_rect(location_rect, data['delivery_location'], font_size=16)
    
    # Date (Bottom) - Anchor Y ~648
    date_bottom_rect = fitz.Rect(140, 671, 310, 691)  # Shifted right to be clearer
    # For the bottom line, we want to center it over the line
    draw_text_in_rect(date_bottom_rect, data['date'], align="center", font_size=14)
    
    for i in range(5):  # Loop through all 5 possible rows
        row = TABLE_ROWS[i]
        y_top = row['y_start'] - 2
        y_bottom = row['y_end'] + 2
        
        # Define rectangles for all three columns
        desc_rect = fitz.Rect(TABLE_COLUMNS['item_description']['x_start'], y_top,
                              TABLE_COLUMNS['item_description']['x_end'], y_bottom)
        qty_rect = fitz.Rect(TABLE_COLUMNS['quantity']['x_start'], y_top,
                             TABLE_COLUMNS['quantity']['x_end'], y_bottom)
        remarks_rect = fitz.Rect(TABLE_COLUMNS['remarks']['x_start'], y_top,
                                 TABLE_COLUMNS['remarks']['x_end'], y_bottom)
        
        if i < len(data['items']):
            item = data['items'][i]
            # Description: Inset x=3, y=4 to definitely avoid grid lines
            draw_text_in_rect(desc_rect, f"{i + 1}. {item['description']}", align="left", inset=(3, 4), font_size=14)
            # Quantity: Centered
            draw_text_in_rect(qty_rect, item['quantity'], align="center", inset=(3, 4), font_size=14)
            # Remarks: Left aligned
            draw_text_in_rect(remarks_rect, item['remarks'], align="left", inset=(3, 4), font_size=14)
        else:
            # If no item, clear. Important to inset to keep grid lines.
            draw_text_in_rect(desc_rect, "", inset=(3, 4))
            draw_text_in_rect(qty_rect, "", inset=(3, 4))
            draw_text_in_rect(remarks_rect, "", inset=(3, 4))
    
    # Save to bytes
    pdf_bytes = doc.tobytes()
    doc.close()
    
    return pdf_bytes


# ============ HTML Template ============

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Delivery Receipt Autofiller</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.5;
            color: #333;
            max-width: 600px;
            margin: 20px auto;
            padding: 0 15px;
            background-color: #f9f9f9;
        }
        h1 { font-size: 24px; margin-bottom: 10px; }
        p { color: #666; margin-bottom: 20px; }
        .card {
            background: #fff;
            border: 1px solid #ddd;
            padding: 20px;
            margin-bottom: 20px;
            border-radius: 4px;
        }
        .form-group { margin-bottom: 15px; }
        label { display: block; font-weight: bold; margin-bottom: 5px; }
        input[type="text"] {
            width: 100%;
            padding: 8px;
            border: 1px solid #ccc;
            border-radius: 4px;
            box-sizing: border-box;
        }
        .item-row { border-top: 1px solid #eee; padding-top: 15px; margin-top: 15px; }
        .btn-primary {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 16px;
            width: 100%;
        }
        .btn-primary:hover { background-color: #0056b3; }
        .error { color: #721c24; background-color: #f8d7da; border: 1px solid #f5c6cb; padding: 10px; border-radius: 4px; margin-bottom: 20px; }
        .hint { font-size: 12px; color: #888; margin-top: 4px; }
    </style>
</head>
<body>
    <h1>Delivery Receipt</h1>
    <p>Fill in the details to generate your PDF.</p>

    {% if error %}
    <div class="error">{{ error }}</div>
    {% endif %}

    <form action="/delivery-receipt" method="post">
        <div class="card">
            <h3>Basic Info</h3>
            <div class="form-group">
                <label for="date">Date</label>
                <input type="text" id="date" name="date" value="{{ today }}">
                <div class="hint">Format: MM/DD/YYYY</div>
            </div>
            <div class="form-group">
                <label for="consignee">Consignee</label>
                <input type="text" id="consignee" name="consignee" required>
            </div>
            <div class="form-group">
                <label for="delivery_location">Delivery Location</label>
                <input type="text" id="delivery_location" name="delivery_location" required>
            </div>
        </div>

        <div class="card">
            <h3>Items</h3>
            <div>
                <label>Item 1</label>
                <div class="form-group">
                    <input type="text" name="item1_description" placeholder="Description" required>
                </div>
                <div class="form-group">
                    <input type="text" name="item1_quantity" placeholder="Quantity">
                </div>
                <div class="form-group">
                    <input type="text" name="item1_remarks" value="No issues" placeholder="Remarks">
                </div>
            </div>

            <div class="item-row">
                <label>Item 2 (Optional)</label>
                <div class="form-group">
                    <input type="text" name="item2_description" placeholder="Description">
                </div>
                <div class="form-group">
                    <input type="text" name="item2_quantity" placeholder="Quantity">
                </div>
                <div class="form-group">
                    <input type="text" name="item2_remarks" value="No issues" placeholder="Remarks">
                </div>
            </div>

            <div class="item-row">
                <label>Item 3 (Optional)</label>
                <div class="form-group">
                    <input type="text" name="item3_description" placeholder="Description">
                </div>
                <div class="form-group">
                    <input type="text" name="item3_quantity" placeholder="Quantity">
                </div>
                <div class="form-group">
                    <input type="text" name="item3_remarks" value="No issues" placeholder="Remarks">
                </div>
            </div>

            <div class="item-row">
                <label>Item 4 (Optional)</label>
                <div class="form-group">
                    <input type="text" name="item4_description" placeholder="Description">
                </div>
                <div class="form-group">
                    <input type="text" name="item4_quantity" placeholder="Quantity">
                </div>
                <div class="form-group">
                    <input type="text" name="item4_remarks" value="No issues" placeholder="Remarks">
                </div>
            </div>

            <div class="item-row">
                <label>Item 5 (Optional)</label>
                <div class="form-group">
                    <input type="text" name="item5_description" placeholder="Description">
                </div>
                <div class="form-group">
                    <input type="text" name="item5_quantity" placeholder="Quantity">
                </div>
                <div class="form-group">
                    <input type="text" name="item5_remarks" value="No issues" placeholder="Remarks">
                </div>
            </div>
        </div>

        <button type="submit" class="btn-primary">Generate Receipt</button>
    </form>
    <footer style="text-align: center; margin-top: 30px; font-size: 12px; color: #999;">
        &copy; 2026 Delivery Receipt Tool
    </footer>
</body>
</html>
'''


# ============ Routes ============

@app.route('/')
def home():
    return redirect('/delivery-receipt')


@app.route('/delivery-receipt', methods=['GET', 'POST'])
def delivery_receipt():
    today = datetime.now().strftime("%m/%d/%Y")
    error = None
    success = None
    
    if request.method == 'POST':
        try:
            date = request.form.get('date', '').strip() or today
            consignee = request.form.get('consignee', '').strip()
            delivery_location = request.form.get('delivery_location', '').strip()
            
            if not consignee:
                return render_template_string(HTML_TEMPLATE, today=today, error='Please enter a consignee name.')
            
            if not delivery_location:
                return render_template_string(HTML_TEMPLATE, today=today, error='Please enter a delivery location.')
            
            items = []
            for i in range(1, 6):
                desc = request.form.get(f'item{i}_description', '').strip()
                if desc:
                    items.append({
                        'description': desc,
                        'quantity': request.form.get(f'item{i}_quantity', '1 unit').strip() or '1 unit',
                        'remarks': request.form.get(f'item{i}_remarks', 'No issues').strip() or 'No issues'
                    })
            
            if not items:
                return render_template_string(HTML_TEMPLATE, today=today, error='Please add at least one item.')
            
            data = {
                'date': date,
                'consignee': consignee,
                'delivery_location': delivery_location,
                'items': items
            }
            
            template_path = os.path.join(BASE_DIR, 'delivery_receipt_template.pdf')
            pdf_bytes = fill_delivery_receipt(data, template_path)
            
            filename = f'Delivery_Receipt_{consignee.replace(" ", "_")}_{date.replace("/", "-")}.pdf'
            
            return Response(
                pdf_bytes,
                mimetype='application/pdf',
                headers={
                    'Content-Disposition': f'attachment; filename="{filename}"'
                }
            )
            
        except Exception as e:
            logger.error(f"Error generating delivery receipt: {e}")
            return render_template_string(HTML_TEMPLATE, today=today, error=f'An error occurred: {str(e)}')
    
    return render_template_string(HTML_TEMPLATE, today=today, error=error, success=success)


# For Vercel
app = app
