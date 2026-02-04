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
    
    # Helper function to replace text area
    def draw_text_in_rect(rect, text, align="left", font_size=10):
        """Draw text in a rectangle with auto-scaling and alignment."""
        # 1. Clear the area
        shape = page.new_shape()
        shape.draw_rect(rect)
        shape.finish(fill=white, color=white)
        shape.commit()
        
        if not text:
            return

        # 2. Auto-scale font size
        current_font_size = font_size
        text_width = page.get_text_length(text, fontname=font_name, fontsize=current_font_size)
        rect_width = rect.width - 4  # 2px padding on each side
        
        while text_width > rect_width and current_font_size > 6:
            current_font_size -= 0.5
            text_width = page.get_text_length(text, fontname=font_name, fontsize=current_font_size)
            
        # 3. Calculate alignment
        y_pos = rect.y1 - ((rect.height - current_font_size) / 2) - 2
        
        if align == "center":
            x_pos = rect.x0 + (rect.width - text_width) / 2
        else:  # left
            x_pos = rect.x0 + 2  # Left padding
            
        text_point = fitz.Point(x_pos, y_pos)
        page.insert_text(text_point, text, fontname=font_name, fontsize=current_font_size, color=black)
    
    # 1. Replace the date at the top (after "Date: ")
    date_rect = fitz.Rect(95, 108, 220, 126)
    draw_text_in_rect(date_rect, data['date'])
    
    # 2. Replace the consignee (after "Consignee: ")
    consignee_rect = fitz.Rect(130, 176, 400, 193)
    draw_text_in_rect(consignee_rect, data['consignee'])
    
    # 3. Replace the delivery location (after "Delivery Location: ")
    location_rect = fitz.Rect(165, 191, 540, 208)
    draw_text_in_rect(location_rect, data['delivery_location'])
    
    # 4. Replace the date at the bottom (with underscores)
    date_bottom_rect = fitz.Rect(72, 522, 220, 540)
    # For the bottom line, we want to center it over the line
    draw_text_in_rect(date_bottom_rect, data['date'], align="center")
    
    # 5. Replace items in the table
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
            # Description: Left aligned
            draw_text_in_rect(desc_rect, f"{i + 1}. {item['description']}", align="left")
            # Quantity: Centered
            draw_text_in_rect(qty_rect, item['quantity'], align="center")
            # Remarks: Left aligned
            draw_text_in_rect(remarks_rect, item['remarks'], align="left")
        else:
            # If no item, clear
            draw_text_in_rect(desc_rect, "")
            draw_text_in_rect(qty_rect, "")
            draw_text_in_rect(remarks_rect, "")
    
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
