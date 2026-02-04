from PIL import Image
import os

img_path = "/Users/jackcheng/.gemini/antigravity/brain/9702b1f8-01e4-4373-8070-fd384d83bf76/uploaded_media_1770182641165.png"
output_path = "/Users/jackcheng/Desktop/projects/autofiller/delivery_receipt_template.pdf"

# Standard A4 size in points at 72 DPI is 595x842
# But for PIL, we should think in pixels and use resolution
# Let's just resize it to exactly 595x842 pixels and save at 72 DPI

img = Image.open(img_path)
if img.mode != 'RGB':
    img = img.convert('RGB')

# Resize to A4 proportions
# Standard points are 595 x 842
# We want to preserve aspect ratio? The image looks like it's a page anyway.
img = img.resize((595, 842), Image.Resampling.LANCZOS)

# Save as PDF at 72 DPI so 1 pixel = 1 point
img.save(output_path, "PDF", resolution=72.0)

print(f"Template created at {output_path} with size 595x842")
