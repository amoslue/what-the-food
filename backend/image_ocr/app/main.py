from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.responses import JSONResponse
from PIL import Image
from fastapi.middleware.cors import CORSMiddleware 
import pytesseract
import io
import re

# IMPORTANT: Set the path to the tesseract executable if it's not in your PATH
# For Windows, uncomment and set this:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
# For Linux/macOS, if you installed via package manager, it might be automatically found.
# If you get 'tesseract is not installed or not in your PATH' error, set it here.

app = FastAPI(
    title="Menu OCR and Structuring Service",
    description="Extracts dish names and descriptions from menu images.",
    version="0.1.0"
)

origins = [
    "http://localhost",
    "http://localhost:3000", # Your React app's address
    # You can add more origins here if your frontend runs on different URLs/ports,
    # or if you have multiple frontend applications.
    # "http://your-production-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,            # List of allowed origins
    allow_credentials=True,           # Allow cookies to be included in cross-origin requests
    allow_methods=["*"],              # Allow all HTTP methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],              # Allow all headers
)
# --- Helper Functions ---

def preprocess_image_for_ocr(image_bytes: bytes) -> Image.Image:
    """
    Loads an image from bytes and performs basic preprocessing for OCR.
    """
    try:
        image = Image.open(io.BytesIO(image_bytes))
        # Convert to grayscale for better OCR results
        image = image.convert("L")
        # You might add more preprocessing here later:
        # e.g., image = ImageOps.autocontrast(image)
        #       image = image.filter(ImageFilter.SHARPEN)
        #       image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS) # Upscale
        return image
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not process image: {e}")

def extract_text_with_ocr(image: Image.Image) -> str:
    """
    Performs OCR on the given PIL Image and returns the raw text.
    """
    try:
        # Using lang='eng' for English. You can add more languages if needed,
        # but ensure Tesseract data for those languages is installed.
        text = pytesseract.image_to_string(image, lang='eng')
        return text
    except pytesseract.TesseractError as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during OCR: {e}")

def structure_menu_text(raw_text: str) -> list[dict]:
    """
    Attempts to structure the raw OCR text into a list of dishes.
    This is a preliminary, rule-based approach. It will need refinement.
    """
    dishes = []
    lines = raw_text.strip().split('\n')
    current_dish_name = ""
    current_dish_desc = ""

    # Simple heuristic: Lines starting with a capital letter or number might be a dish name.
    # Lines following that with smaller text are descriptions.
    # This is *highly* dependent on menu format and will need NLP for robustness.

    for line in lines:
        line = line.strip()
        if not line: # Skip empty lines
            continue

        # Simple pattern to identify potential dish names:
        # - Starts with a capital letter or number, and seems like a distinct item
        # - Not too long (to avoid picking up paragraphs as names)
        # - Does not look like a price (e.g., starts with $, £, €, or just numbers)

        # Let's try to detect common price patterns and skip them if they appear as main lines
        price_pattern = re.compile(r'^\s*([$£€]?\d+(\.\d{1,2})?|\d+(\.\d{1,2})?\s*[€$£]?)\s*$')
        if price_pattern.match(line):
             # This line seems to be just a price, skip it for now.
             continue

        # Heuristic 1: If a line is predominantly uppercase, consider it a potential dish name
        # Heuristic 2: If a line is short and starts with a capital letter/number
        # Heuristic 3: Use a more complex regex to identify potential names vs. descriptions
        
        # A more robust approach might look for specific keywords, or use an NLP model
        # For now, a simple approach: if it looks like a new item, start a new dish.
        # This will be very basic and needs improvement.
        
        # Let's assume a new line that is not excessively long and not empty could be a new dish name
        # if it's potentially an item. For now, very simple.
        
        is_potential_dish_name = False
        if len(line) < 60 and line[0].isupper() or line[0].isdigit():
            # Exclude lines that are mostly numbers or very short common words
            if not (len(line.split()) <= 2 and all(char.isdigit() or not char.isalpha() for char in line)):
                 is_potential_dish_name = True

        if is_potential_dish_name:
            if current_dish_name and current_dish_desc:
                dishes.append({"name": current_dish_name.strip(), "description": current_dish_desc.strip()})
            elif current_dish_name and not current_dish_desc:
                 # If we have a name but no desc before a new name, use the name as description too or leave empty
                 dishes.append({"name": current_dish_name.strip(), "description": ""})
            
            current_dish_name = line
            current_dish_desc = ""
        else:
            if current_dish_name:
                current_dish_desc += " " + line
            # else: This line is a description without a preceding name (orphan), ignore for now.

    # Add the last dish if any
    if current_dish_name:
        dishes.append({"name": current_dish_name.strip(), "description": current_dish_desc.strip()})
    
    # Post-processing: Remove empty descriptions if they are just whitespace
    for dish in dishes:
        if not dish["description"].strip():
            dish["description"] = ""
            
    # Filter out dishes with very short names or names that look like generic text
    # This is another heuristic that might need adjustment
    filtered_dishes = []
    for dish in dishes:
        name = dish["name"].strip()
        if len(name) > 3 and "ingredien" not in name.lower() and "menu" not in name.lower() and not name.isdigit():
            filtered_dishes.append(dish)

    return filtered_dishes


# --- API Endpoint ---

@app.post("/extract_menu_data/")
async def extract_menu_data(file: UploadFile = File(...)):
    """
    Receives a menu image, performs OCR, and extracts structured dish information.
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Uploaded file is not an image.")

    image_bytes = await file.read()

    # 1. Preprocess image
    pil_image = preprocess_image_for_ocr(image_bytes)

    # 2. Perform OCR
    raw_text = extract_text_with_ocr(pil_image)

    # 3. Structure the text
    structured_data = structure_menu_text(raw_text)

    # For debugging purposes, you might want to return the raw text as well
    return JSONResponse(content={
        "raw_ocr_output": raw_text, # Useful for debugging and understanding OCR quality
        "structured_menu_data": structured_data
    })

# --- To run the application ---
# From the `image_preprocessing_ocr` directory (the one containing app/):
# uvicorn app.main:app --reload --port 8000