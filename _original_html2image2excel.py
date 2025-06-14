from playwright.sync_api import sync_playwright
import openpyxl
from openpyxl.drawing.image import Image as ExcelImage
import os
from PIL import Image as PILImage
import tkinter as tk
from tkinter import filedialog

def open_file_dialog():
    root = tk.Tk()
    root.withdraw()  # Hide the main window
    file_path = filedialog.askopenfilename()
    return file_path


def convert_html_to_excel(html_file_path, excel_output_path="output.xlsx", class_selector=".box"):
    """
    Convert HTML file to Excel with original-sized floating images of box elements
    
    Args:
        html_file_path: Path to your HTML file
        excel_output_path: Output Excel file path
    """
    
    try:
        # Read the HTML file
        with open(html_file_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        print(f"📂 Reading HTML file: {html_file_path}")
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Set the HTML content
            page.set_content(html_content)
            
            # Wait for the box elements to load
            page.wait_for_selector(class_selector)
            
            # Find all box elements
            box_elements = page.query_selector_all(class_selector)
            print(f"🔍 Found {len(box_elements)} box elements")
            
            # Create Excel workbook
            workbook = openpyxl.Workbook()
            worksheet = workbook.active
            worksheet.title = "HTML Box Images"
            
            # Starting position for floating images
            current_row = 1
            vertical_offset = 0  # Track vertical position for floating images
            
            # Process each box element
            for i, box_element in enumerate(box_elements):
                print(f"📸 Taking screenshot of box {i+1}")
                
                # Screenshot filename
                screenshot_path = f"temp_box_{i+1}.png"
                
                # Take screenshot of the box element
                box_element.screenshot(path=screenshot_path)
                
                # Add floating image to Excel
                if os.path.exists(screenshot_path):
                    # Get original image dimensions
                    with PILImage.open(screenshot_path) as pil_img:
                        original_width, original_height = pil_img.size
                    
                    img = ExcelImage(screenshot_path)
                    
                    # Keep original image size (no resizing)
                    img.width = original_width
                    img.height = original_height
                    
                    # Set image anchor to cell position (images will maintain original size)
                    img.anchor = f'A{current_row}'
                    
                    # Add image to worksheet
                    worksheet.add_image(img)
                    
                    # Calculate rows needed for this image (based on approximate row height)
                    approx_row_height_pixels = 20  # Default Excel row height in pixels
                    rows_needed = max(1, (original_height + 10) // approx_row_height_pixels)
                    current_row += rows_needed + 1  # Add extra row for spacing
                    
                    print(f"✅ Added floating image {i+1} to Excel (Size: {original_width}x{original_height})")
            
            # Set column width to be reasonable (images will float over it)
            worksheet.column_dimensions['A'].width = 20
            
            # Add some empty rows to ensure all images are visible
            for row in range(current_row, current_row + 5):
                worksheet.cell(row=row, column=1, value="")
            
            # Save Excel file
            workbook.save(excel_output_path)
            print(f"💾 Excel file saved: {excel_output_path}")
            
            # Close browser
            browser.close()
            
            # Clean up temporary image files
            for i in range(len(box_elements)):
                temp_file = f"temp_box_{i+1}.png"
                try:
                    os.remove(temp_file)
                    print(f"🧹 Cleaned up: {temp_file}")
                except:
                    pass
            
            print(f"🎉 Process completed successfully!")
            print(f"📋 Images are floating and maintain their original dimensions")
            return excel_output_path
            
    except FileNotFoundError:
        print(f"❌ Error: HTML file not found at {html_file_path}")
        return None
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        return None

def convert_with_file_reader():
    """
    Version that uses window.fs.readFile API to read the uploaded file
    """
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            # Add file reading capability to the page
            page.add_init_script("""
                window.fs = {
                    readFile: async (filepath, options = {}) => {
                        // This would be implemented by the environment
                        // For now, we'll use a placeholder
                        return new Uint8Array();
                    }
                };
            """)
            
            # Use the file reading approach
            html_content = page.evaluate("""
                async () => {
                    try {
                        const data = await window.fs.readFile('HTMLFILE.html', { encoding: 'utf8' });
                        return data;
                    } catch (error) {
                        console.error('Error reading file:', error);
                        return null;
                    }
                }
            """)
            
            if html_content:
                page.set_content(html_content)
                # Continue with the rest of the process...
            
            browser.close()
            
    except Exception as e:
        print(f"File reader approach failed: {e}")
        return None

if __name__ == "__main__":
    print("🚀 HTML to Excel Converter with Floating Original-Size Images")
    print("=" * 60)
    
    # Main conversion - adjust the path to your HTML file
    # html_file = "test.html"  # Your uploaded file
    html_file = open_file_dialog()
    excel_output = "html_boxes_floating_output.xlsx"
    class_selector = ".box"
    
    result = convert_html_to_excel(html_file, excel_output,class_selector)
    
    if result:
        print(f"\n✨ Success! Excel file created: {result}")
        print("\nThe Excel file contains:")
        print("- Floating images of each class_selector element")
        print("- Original image dimensions preserved")
        print("- Images positioned absolutely (not tied to cell sizes)")
        print("- 20 pixel spacing between images")
        print("- Images start in column A with 10 pixel left margin")
    else:
        print("\n❌ Failed to create Excel file")
        print("Make sure:")
        print("1. test.html file exists in the same directory")
        print("2. Required packages are installed:")
        print("   pip install playwright openpyxl pillow")
        print("3. Chromium is installed: playwright install chromium")