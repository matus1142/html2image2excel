from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
import openpyxl
from PIL import Image as PILImage
from openpyxl.drawing.image import Image as ExcelImage
import os


def convert_html_to_excel(html_file_path, excel_output_path="output.xlsx", class_selector=".box"):
    """
    Convert HTML file to Excel with original-sized floating images of box elements
    
    Args:
        html_file_path: Path to your HTML file
        excel_output_path: Output Excel file path
    """
    
    try:
        
        with sync_playwright() as p:
            # Launch browser
            browser = p.chromium.launch(headless=False)
            page = browser.new_page()
            
            # Open the HTML on browser
            print(f"📂 Opening HTML file: {html_file_path}")
            page.goto(f"file://{html_file_path}")
            
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
    


def extract_html_content(extracted_html_file_path: str,html_content: str):
    """Parse HTML content and find 'Uncovered Link' text between h4 elements"""
    soup = BeautifulSoup(html_content, 'html.parser')
    found_results = []
    
    extract_uncovered_link_boxes=''

    # Find all h4 elements
    h4_elements = soup.find_all('h4')
    
    for h4 in h4_elements:
        
        # Find all p tags that come after this h4 until the next h4
        current_element = h4

        # Initialize variables
        collected_text = ''
        found_status = False
        
        while current_element:
            
            # Check for 'Uncovered Link' in child
            if 'Uncovered Link' in current_element.get_text(strip=True):
                found_status = True
            
            # Collect text
            collected_text = collected_text + str(current_element)
            
            # If we hit the end of the document, stop
            if current_element.next_sibling is None and found_status == True:
                extract_uncovered_link_boxes =  extract_uncovered_link_boxes + '<div class="image-box">' + collected_text + '</div>' + '\n'
                break
            elif current_element.next_sibling is None and found_status == False:
                break

            # If we hit another h4, stop searching and collect text
            if current_element.next_sibling.name == 'h4' and found_status == True:
                extract_uncovered_link_boxes =  extract_uncovered_link_boxes + '<div class="image-box">' + collected_text + '</div>' + '\n'
                break
            # If we hit another h4, stop searching
            elif current_element.next_sibling.name == 'h4' and found_status == False:
                break
            else: 
                # Move to the next element
                current_element = current_element.next_sibling
    
    # Create the HTML content
    extracted_html_content = f'''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Document</title>
</head>
<body>
    {extract_uncovered_link_boxes}
</body>
</html>
'''
    # Write the HTML content to a file
    with open(extracted_html_file_path, "w") as f:
        f.write(extracted_html_content)

    return found_results