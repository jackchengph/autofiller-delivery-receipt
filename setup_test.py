import fitz

def create_test_pdf():
    doc = fitz.open()
    page = doc.new_page()
    
    # Add some labels
    text_writer = fitz.TextWriter(page.rect)
    
    # Form fields
    text_writer.append((50, 100), "Full Name:", fontsize=12)
    text_writer.append((50, 150), "Date of Birth:", fontsize=12)
    text_writer.append((50, 200), "Student ID:", fontsize=12)
    
    # Write to page
    text_writer.write_text(page)
    
    doc.save("test_form.pdf")
    print("Created test_form.pdf")

def create_test_data():
    import json
    data = {
        "Full Name": "Alice Smith",
        "Date of Birth": "1999-01-01",
        "Student ID": "S12345678"
    }
    with open("test_data.json", "w") as f:
        json.dump(data, f, indent=2)
    print("Created test_data.json")

if __name__ == "__main__":
    create_test_pdf()
    create_test_data()
    print("\nNow run: python autofill.py test_form.pdf test_data.json")
