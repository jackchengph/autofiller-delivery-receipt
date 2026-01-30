#!/usr/bin/env python3
"""
Delivery Receipt PDF Filler
A tool to autofill the delivery receipt template with user-provided information.
"""

import fitz  # PyMuPDF
import os
from datetime import datetime

# Define the field positions based on the template analysis
# These are the positions where we'll place the new text (replacing the old text)
FIELD_POSITIONS = {
    'date': {
        'bbox': (103, 110.9, 200, 123.2),  # Date at the top
        'original_text': '12/22/2025'
    },
    'consignee': {
        'bbox': (136, 178.5, 300, 190.8),  # After "Consignee: "
        'original_text': 'Back to Basics'
    },
    'delivery_location': {
        'bbox': (172, 193.1, 500, 205.4),  # After "Delivery Location: "
        'original_text': '30 Maginhawa, Diliman Quezon City'
    },
    'date_bottom': {
        'bbox': (72, 524.9, 220, 537.2),  # Date at the bottom
        'original_text': '______12/22/2025_______'
    }
}

# Table row positions for items
TABLE_ROWS = [
    {'y_start': 276.9, 'y_end': 289.2},  # Row 1
    {'y_start': 300.8, 'y_end': 313.1},  # Row 2
]

# Column positions
TABLE_COLUMNS = {
    'item_description': {'x_start': 95.25, 'x_end': 290},
    'quantity': {'x_start': 306, 'x_end': 380},
    'remarks': {'x_start': 389.25, 'x_end': 520}
}


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """Print a nice header for the application."""
    print("\n" + "=" * 60)
    print("       📦 DELIVERY RECEIPT AUTOFILLER 📦")
    print("=" * 60)
    print()


def print_separator():
    """Print a separator line."""
    print("-" * 60)


def get_user_input():
    """Collect all user inputs for the delivery receipt."""
    data = {}
    
    clear_screen()
    print_header()
    print("Please provide the following information:\n")
    
    # 1. Date
    print_separator()
    print("📅 DATE")
    print("   (Format: MM/DD/YYYY or press Enter for today's date)")
    date_input = input("   Enter date: ").strip()
    if not date_input:
        date_input = datetime.now().strftime("%m/%d/%Y")
    data['date'] = date_input
    print(f"   ✓ Date set to: {date_input}")
    print()
    
    # 2. Consignee
    print_separator()
    print("👤 CONSIGNEE")
    print("   (The person/company receiving the goods)")
    consignee = input("   Enter consignee name: ").strip()
    data['consignee'] = consignee if consignee else "Back to Basics"
    print(f"   ✓ Consignee set to: {data['consignee']}")
    print()
    
    # 3. Delivery Location
    print_separator()
    print("📍 DELIVERY LOCATION")
    print("   (The address where goods are delivered)")
    location = input("   Enter delivery location: ").strip()
    data['delivery_location'] = location if location else "30 Maginhawa, Diliman Quezon City"
    print(f"   ✓ Delivery location set to: {data['delivery_location']}")
    print()
    
    # 4. Items (can add multiple)
    print_separator()
    print("📦 ITEMS")
    print("   (You can add up to 2 items)")
    
    items = []
    for i in range(2):
        print(f"\n   --- Item {i + 1} ---")
        description = input(f"   Item description (or press Enter to skip): ").strip()
        
        if not description:
            if i == 0:
                # Default first item
                items.append({
                    'description': 'Hand Soap Starter Kit w/ Ribbon',
                    'quantity': '36 boxes',
                    'remarks': 'No issues'
                })
                print("   ✓ Using default item 1")
            continue
        
        quantity = input(f"   Quantity: ").strip()
        if not quantity:
            quantity = "1 unit"
        
        remarks = input(f"   Remarks (or press Enter for 'No issues'): ").strip()
        if not remarks:
            remarks = "No issues"
        
        items.append({
            'description': description,
            'quantity': quantity,
            'remarks': remarks
        })
        print(f"   ✓ Item {i + 1} added: {description}")
    
    # Ensure we have at least one item
    if not items:
        items = [
            {'description': 'Hand Soap Starter Kit w/ Ribbon', 'quantity': '36 boxes', 'remarks': 'No issues'},
            {'description': 'Hand Soap Starter Kit', 'quantity': '25 boxes', 'remarks': 'No issues'}
        ]
    
    data['items'] = items
    
    return data


def confirm_data(data):
    """Display the collected data and ask for confirmation."""
    clear_screen()
    print_header()
    print("📋 PLEASE REVIEW YOUR INFORMATION:\n")
    print_separator()
    
    print(f"📅 DATE:              {data['date']}")
    print(f"👤 CONSIGNEE:         {data['consignee']}")
    print(f"📍 DELIVERY LOCATION: {data['delivery_location']}")
    print()
    print("📦 ITEMS:")
    print("   " + "-" * 55)
    print(f"   {'Description':<30} {'Quantity':<12} {'Remarks':<12}")
    print("   " + "-" * 55)
    
    for i, item in enumerate(data['items'], 1):
        desc = item['description'][:28] + ".." if len(item['description']) > 30 else item['description']
        print(f"   {desc:<30} {item['quantity']:<12} {item['remarks']:<12}")
    
    print("   " + "-" * 55)
    print_separator()
    print()
    
    while True:
        confirm = input("Is this information correct? (yes/no): ").strip().lower()
        if confirm in ['yes', 'y']:
            return True
        elif confirm in ['no', 'n']:
            return False
        else:
            print("Please enter 'yes' or 'no'")


def fill_pdf(data, template_path, output_path):
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
    for i, item in enumerate(data['items'][:2]):  # Max 2 items
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


def main():
    """Main function to run the delivery receipt filler."""
    template_path = os.path.join(os.path.dirname(__file__), 'delivery_receipt_template.pdf')
    output_dir = os.path.join(os.path.dirname(__file__), 'outputs')
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Generate output filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(output_dir, f'delivery_receipt_filled_{timestamp}.pdf')
    
    while True:
        # Get user input
        data = get_user_input()
        
        # Confirm the data
        if confirm_data(data):
            break
        else:
            print("\nLet's start over...")
            input("Press Enter to continue...")
    
    # Fill the PDF
    clear_screen()
    print_header()
    print("⏳ Processing your delivery receipt...\n")
    
    try:
        result_path = fill_pdf(data, template_path, output_path)
        print("✅ SUCCESS! Your delivery receipt has been created!\n")
        print_separator()
        print(f"📄 Output file: {result_path}")
        print_separator()
        print()
        
        # Ask if user wants to open the file
        open_file = input("Would you like to open the PDF? (yes/no): ").strip().lower()
        if open_file in ['yes', 'y']:
            os.system(f'open "{result_path}"')
            
    except Exception as e:
        print(f"❌ ERROR: Failed to create delivery receipt")
        print(f"   Details: {str(e)}")
        return 1
    
    print("\nThank you for using Delivery Receipt Autofiller! 👋")
    return 0


if __name__ == "__main__":
    exit(main())
