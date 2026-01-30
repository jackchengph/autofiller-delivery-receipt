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
    {'y_start': 276.9, 'y_end': 289.2},
    {'y_start': 300.8, 'y_end': 313.1},
]

TABLE_COLUMNS = {
    'item_description': {'x_start': 95.25, 'x_end': 290},
    'quantity': {'x_start': 306, 'x_end': 380},
    'remarks': {'x_start': 389.25, 'x_end': 520}
}


def fill_delivery_receipt(data, template_path):
    """Fill the PDF template with the provided data and return bytes."""
    
    doc = fitz.open(template_path)
    page = doc[0]
    
    white = fitz.pdfcolor["white"]
    black = fitz.pdfcolor["black"]
    font_name = "helv"
    
    def cover_and_write(rect, new_text, font_size=10):
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(fill=white, color=white)
        shape.commit()
        text_point = fitz.Point(rect.x0, rect.y1 - 2)
        page.insert_text(text_point, new_text, fontname=font_name, fontsize=font_size, color=black)
    
    # Fill fields
    date_rect = fitz.Rect(95, 108, 220, 126)
    cover_and_write(date_rect, data['date'])
    
    consignee_rect = fitz.Rect(130, 176, 400, 193)
    cover_and_write(consignee_rect, data['consignee'])
    
    location_rect = fitz.Rect(165, 191, 540, 208)
    cover_and_write(location_rect, data['delivery_location'])
    
    date_bottom_rect = fitz.Rect(72, 522, 220, 540)
    cover_and_write(date_bottom_rect, f" ______{data['date']}_______ ")
    
    for i, item in enumerate(data['items'][:2]):
        row = TABLE_ROWS[i]
        y_top = row['y_start'] - 2
        y_bottom = row['y_end'] + 2
        
        desc_rect = fitz.Rect(TABLE_COLUMNS['item_description']['x_start'], y_top,
                              TABLE_COLUMNS['item_description']['x_end'], y_bottom)
        cover_and_write(desc_rect, f"{i + 1}. {item['description']}")
        
        qty_rect = fitz.Rect(TABLE_COLUMNS['quantity']['x_start'], y_top,
                             TABLE_COLUMNS['quantity']['x_end'], y_bottom)
        cover_and_write(qty_rect, item['quantity'])
        
        remarks_rect = fitz.Rect(TABLE_COLUMNS['remarks']['x_start'], y_top,
                                 TABLE_COLUMNS['remarks']['x_end'], y_bottom)
        cover_and_write(remarks_rect, item['remarks'])
    
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
            item1_desc = request.form.get('item1_description', '').strip()
            if item1_desc:
                items.append({
                    'description': item1_desc,
                    'quantity': request.form.get('item1_quantity', '1 unit').strip() or '1 unit',
                    'remarks': request.form.get('item1_remarks', 'No issues').strip() or 'No issues'
                })
            
            item2_desc = request.form.get('item2_description', '').strip()
            if item2_desc:
                items.append({
                    'description': item2_desc,
                    'quantity': request.form.get('item2_quantity', '1 unit').strip() or '1 unit',
                    'remarks': request.form.get('item2_remarks', 'No issues').strip() or 'No issues'
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
