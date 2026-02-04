import os
import json
import logging
from datetime import datetime
from flask import Flask, render_template, request, send_file, flash, redirect, url_for
from werkzeug.utils import secure_filename

# Import the PDF filler function from delivery_receipt_filler
import fitz  # PyMuPDF

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = 'supersecretkey'  # For flash messages

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'outputs'
ALLOWED_EXTENSIONS = {'pdf', 'json'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ============ Delivery Receipt Filler Logic ============

# Define the field positions based on the template analysis
TABLE_ROWS = [
    {'y_start': 276.9, 'y_end': 289.2},  # Row 1
    {'y_start': 300.8, 'y_end': 313.1},  # Row 2
    {'y_start': 324.7, 'y_end': 337.0},  # Row 3
    {'y_start': 348.6, 'y_end': 360.9},  # Row 4
    {'y_start': 372.5, 'y_end': 384.8},  # Row 5
]

TABLE_COLUMNS = {
    'item_description': {'x_start': 95.25, 'x_end': 290},
    'quantity': {'x_start': 306, 'x_end': 380},
    'remarks': {'x_start': 389.25, 'x_end': 520}
}


def fill_delivery_receipt(data, template_path, output_path):
    """Fill the PDF template with the provided data."""
    
    # Open the template
    doc = fitz.open(template_path)
    page = doc[0]
    
    # Define colors
    white = fitz.pdfcolor["white"]
    black = fitz.pdfcolor["black"]
    
    # Font settings
    font_name = "helv"  # Helvetica
    font_size = 10
    
    # Helper function to replace text area
    def cover_and_write(rect, new_text, font_size=10):
        """Cover the original text with white and write new text."""
        # Create a white rectangle to cover the original text
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(fill=white, color=white)
        shape.commit()
        
        # Write the new text
        text_point = fitz.Point(rect.x0, rect.y1 - 2)  # Position at bottom-left of rect
        page.insert_text(text_point, new_text, fontname=font_name, fontsize=font_size, color=black)
    
    # 1. Replace the date at the top (after "Date: ")
    date_rect = fitz.Rect(95, 108, 220, 126)
    cover_and_write(date_rect, data['date'])
    
    # 2. Replace the consignee (after "Consignee: ")
    consignee_rect = fitz.Rect(130, 176, 400, 193)
    cover_and_write(consignee_rect, data['consignee'])
    
    # 3. Replace the delivery location (after "Delivery Location: ")
    location_rect = fitz.Rect(165, 191, 540, 208)
    cover_and_write(location_rect, data['delivery_location'])
    
    # 4. Replace the date at the bottom (with underscores)
    date_bottom_rect = fitz.Rect(72, 522, 220, 540)
    date_with_underscores = f" ______{data['date']}_______ "
    cover_and_write(date_bottom_rect, date_with_underscores)
    
    # 5. Replace items in the table
    for i, item in enumerate(data['items'][:5]):  # Max 5 items
        row = TABLE_ROWS[i]
        y_top = row['y_start'] - 2
        y_bottom = row['y_end'] + 2
        
        # Item description (with number prefix)
        desc_rect = fitz.Rect(
            TABLE_COLUMNS['item_description']['x_start'],
            y_top,
            TABLE_COLUMNS['item_description']['x_end'],
            y_bottom
        )
        cover_and_write(desc_rect, f"{i + 1}. {item['description']}")
        
        # Quantity
        qty_rect = fitz.Rect(
            TABLE_COLUMNS['quantity']['x_start'],
            y_top,
            TABLE_COLUMNS['quantity']['x_end'],
            y_bottom
        )
        cover_and_write(qty_rect, item['quantity'])
        
        # Remarks
        remarks_rect = fitz.Rect(
            TABLE_COLUMNS['remarks']['x_start'],
            y_top,
            TABLE_COLUMNS['remarks']['x_end'],
            y_bottom
        )
        cover_and_write(remarks_rect, item['remarks'])
    
    # Save the modified PDF
    doc.save(output_path)
    doc.close()
    
    return output_path


# ============ Routes ============

@app.route('/')
def home():
    """Redirect to delivery receipt page."""
    return redirect(url_for('delivery_receipt'))


@app.route('/delivery-receipt', methods=['GET', 'POST'])
def delivery_receipt():
    """Handle delivery receipt form and PDF generation."""
    today = datetime.now().strftime("%m/%d/%Y")
    
    if request.method == 'POST':
        try:
            # Get form data
            date = request.form.get('date', '').strip()
            if not date:
                date = today
            
            consignee = request.form.get('consignee', '').strip()
            delivery_location = request.form.get('delivery_location', '').strip()
            
            # Validate required fields
            if not consignee:
                flash('Please enter a consignee name.', 'error')
                return redirect(url_for('delivery_receipt'))
            
            if not delivery_location:
                flash('Please enter a delivery location.', 'error')
                return redirect(url_for('delivery_receipt'))
            
            # Get items
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
                flash('Please add at least one item.', 'error')
                return redirect(url_for('delivery_receipt'))
            
            # Prepare data dictionary
            data = {
                'date': date,
                'consignee': consignee,
                'delivery_location': delivery_location,
                'items': items
            }
            
            # Generate PDF
            template_path = os.path.join(os.path.dirname(__file__), 'delivery_receipt_template.pdf')
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = f'delivery_receipt_filled_{timestamp}.pdf'
            output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)
            
            fill_delivery_receipt(data, template_path, output_path)
            
            # Return the generated PDF
            return send_file(
                output_path,
                as_attachment=True,
                download_name=f'Delivery_Receipt_{consignee.replace(" ", "_")}_{date.replace("/", "-")}.pdf'
            )
            
        except Exception as e:
            logger.error(f"Error generating delivery receipt: {e}")
            flash(f'An error occurred: {str(e)}', 'error')
            return redirect(url_for('delivery_receipt'))
    
    return render_template('delivery_receipt.html', today=today)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
