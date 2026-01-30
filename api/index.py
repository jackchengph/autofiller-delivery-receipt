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
    <title>📦 Delivery Receipt Autofiller</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-gradient-start: #0f0c29;
            --bg-gradient-mid: #302b63;
            --bg-gradient-end: #24243e;
            --card-bg: rgba(255, 255, 255, 0.05);
            --card-border: rgba(255, 255, 255, 0.1);
            --text-primary: #ffffff;
            --text-secondary: rgba(255, 255, 255, 0.7);
            --text-muted: rgba(255, 255, 255, 0.5);
            --accent-primary: #6366f1;
            --accent-secondary: #8b5cf6;
            --accent-success: #10b981;
            --input-bg: rgba(255, 255, 255, 0.08);
            --input-border: rgba(255, 255, 255, 0.15);
            --input-focus: rgba(99, 102, 241, 0.5);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
            background: linear-gradient(135deg, var(--bg-gradient-start) 0%, var(--bg-gradient-mid) 50%, var(--bg-gradient-end) 100%);
            min-height: 100vh;
            color: var(--text-primary);
            line-height: 1.6;
        }
        .bg-orbs { position: fixed; top: 0; left: 0; width: 100%; height: 100%; z-index: -1; overflow: hidden; }
        .orb { position: absolute; border-radius: 50%; filter: blur(80px); opacity: 0.4; animation: float 20s ease-in-out infinite; }
        .orb-1 { width: 400px; height: 400px; background: linear-gradient(135deg, #6366f1, #8b5cf6); top: -100px; right: -100px; }
        .orb-2 { width: 300px; height: 300px; background: linear-gradient(135deg, #ec4899, #f43f5e); bottom: -50px; left: -50px; animation-delay: -5s; }
        .orb-3 { width: 250px; height: 250px; background: linear-gradient(135deg, #06b6d4, #3b82f6); top: 50%; left: 50%; animation-delay: -10s; }
        @keyframes float { 0%, 100% { transform: translate(0, 0) scale(1); } 25% { transform: translate(30px, -30px) scale(1.05); } 50% { transform: translate(-20px, 20px) scale(0.95); } 75% { transform: translate(-30px, -20px) scale(1.02); } }
        .container { max-width: 800px; margin: 0 auto; padding: 40px 20px; }
        header { text-align: center; margin-bottom: 40px; }
        .logo { font-size: 3rem; margin-bottom: 10px; animation: bounce 2s ease-in-out infinite; }
        @keyframes bounce { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        h1 { font-size: 2.5rem; font-weight: 700; background: linear-gradient(135deg, #fff 0%, #c7d2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin-bottom: 10px; }
        header p { color: var(--text-secondary); font-size: 1.1rem; }
        .flash-messages { margin-bottom: 20px; }
        .flash-message { background: linear-gradient(135deg, rgba(16, 185, 129, 0.2), rgba(16, 185, 129, 0.1)); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 12px; padding: 15px 20px; margin-bottom: 10px; color: #6ee7b7; animation: slideIn 0.3s ease-out; }
        .flash-message.error { background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(239, 68, 68, 0.1)); border-color: rgba(239, 68, 68, 0.3); color: #fca5a5; }
        @keyframes slideIn { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .glass-card { background: var(--card-bg); backdrop-filter: blur(20px); -webkit-backdrop-filter: blur(20px); border: 1px solid var(--card-border); border-radius: 24px; padding: 30px; margin-bottom: 25px; transition: transform 0.3s ease, box-shadow 0.3s ease; }
        .glass-card:hover { transform: translateY(-2px); box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3); }
        .section-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; flex-wrap: wrap; }
        .section-icon { font-size: 1.5rem; }
        .section-title { font-size: 1.25rem; font-weight: 600; }
        .section-subtitle { font-size: 0.9rem; color: var(--text-muted); margin-left: auto; }
        .form-group { margin-bottom: 20px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
        @media (max-width: 600px) { .form-row { grid-template-columns: 1fr; } }
        label { display: block; font-size: 0.9rem; font-weight: 500; color: var(--text-secondary); margin-bottom: 8px; }
        input[type="text"], textarea { width: 100%; padding: 14px 18px; background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 12px; color: var(--text-primary); font-size: 1rem; font-family: inherit; transition: all 0.3s ease; }
        input[type="text"]:focus, textarea:focus { outline: none; border-color: var(--accent-primary); box-shadow: 0 0 0 4px var(--input-focus); background: rgba(255, 255, 255, 0.1); }
        input[type="text"]::placeholder { color: var(--text-muted); }
        .item-card { background: rgba(255, 255, 255, 0.03); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 16px; padding: 20px; margin-bottom: 15px; position: relative; }
        .item-number { position: absolute; top: -10px; left: 20px; background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)); color: white; font-size: 0.8rem; font-weight: 600; padding: 4px 12px; border-radius: 20px; }
        .btn { display: inline-flex; align-items: center; justify-content: center; gap: 10px; padding: 16px 32px; font-size: 1rem; font-weight: 600; font-family: inherit; border: none; border-radius: 14px; cursor: pointer; transition: all 0.3s ease; text-decoration: none; }
        .btn-primary { background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary)); color: white; box-shadow: 0 4px 20px rgba(99, 102, 241, 0.4); }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 8px 30px rgba(99, 102, 241, 0.5); }
        .btn-secondary { background: rgba(255, 255, 255, 0.1); color: var(--text-primary); border: 1px solid var(--card-border); }
        .btn-secondary:hover { background: rgba(255, 255, 255, 0.15); }
        .button-group { display: flex; gap: 15px; margin-top: 30px; }
        .button-group .btn { flex: 1; }
        footer { text-align: center; padding: 30px; color: var(--text-muted); font-size: 0.9rem; }
        .hint { font-size: 0.8rem; color: var(--text-muted); margin-top: 6px; }
    </style>
</head>
<body>
    <div class="bg-orbs">
        <div class="orb orb-1"></div>
        <div class="orb orb-2"></div>
        <div class="orb orb-3"></div>
    </div>
    <div class="container">
        <header>
            <div class="logo">📦</div>
            <h1>Delivery Receipt Autofiller</h1>
            <p>Fill in the details below to generate your delivery receipt</p>
        </header>
        <main>
            {% if error %}
            <div class="flash-messages">
                <div class="flash-message error">{{ error }}</div>
            </div>
            {% endif %}
            {% if success %}
            <div class="flash-messages">
                <div class="flash-message">{{ success }}</div>
            </div>
            {% endif %}
            <form action="/delivery-receipt" method="post" id="receipt-form">
                <div class="glass-card">
                    <div class="section-header">
                        <span class="section-icon">📋</span>
                        <span class="section-title">Basic Information</span>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label for="date">📅 Date</label>
                            <input type="text" id="date" name="date" placeholder="MM/DD/YYYY" value="{{ today }}">
                            <p class="hint">Leave blank for today's date</p>
                        </div>
                        <div class="form-group">
                            <label for="consignee">👤 Consignee</label>
                            <input type="text" id="consignee" name="consignee" placeholder="Recipient name or company" required>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="delivery_location">📍 Delivery Location</label>
                        <input type="text" id="delivery_location" name="delivery_location" placeholder="Full delivery address" required>
                    </div>
                </div>
                <div class="glass-card">
                    <div class="section-header">
                        <span class="section-icon">📦</span>
                        <span class="section-title">Items</span>
                        <span class="section-subtitle">Up to 2 items</span>
                    </div>
                    <div class="item-card">
                        <span class="item-number">Item 1</span>
                        <div class="form-group">
                            <label for="item1_description">Item Description</label>
                            <input type="text" id="item1_description" name="item1_description" placeholder="e.g., Hand Soap Starter Kit" required>
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="item1_quantity">Quantity</label>
                                <input type="text" id="item1_quantity" name="item1_quantity" placeholder="e.g., 36 boxes">
                            </div>
                            <div class="form-group">
                                <label for="item1_remarks">Remarks</label>
                                <input type="text" id="item1_remarks" name="item1_remarks" placeholder="e.g., No issues" value="No issues">
                            </div>
                        </div>
                    </div>
                    <div class="item-card">
                        <span class="item-number">Item 2</span>
                        <div class="form-group">
                            <label for="item2_description">Item Description (Optional)</label>
                            <input type="text" id="item2_description" name="item2_description" placeholder="Leave blank to skip">
                        </div>
                        <div class="form-row">
                            <div class="form-group">
                                <label for="item2_quantity">Quantity</label>
                                <input type="text" id="item2_quantity" name="item2_quantity" placeholder="e.g., 25 boxes">
                            </div>
                            <div class="form-group">
                                <label for="item2_remarks">Remarks</label>
                                <input type="text" id="item2_remarks" name="item2_remarks" placeholder="e.g., No issues" value="No issues">
                            </div>
                        </div>
                    </div>
                </div>
                <div class="button-group">
                    <button type="button" class="btn btn-secondary" onclick="clearForm()">🗑️ Clear Form</button>
                    <button type="submit" class="btn btn-primary">✨ Generate Receipt</button>
                </div>
            </form>
        </main>
        <footer>
            <p>Delivery Receipt Autofiller • Deployed on Vercel</p>
        </footer>
    </div>
    <script>
        function clearForm() {
            document.getElementById('receipt-form').reset();
            document.getElementById('date').value = '{{ today }}';
            document.getElementById('item1_remarks').value = 'No issues';
            document.getElementById('item2_remarks').value = 'No issues';
        }
    </script>
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
