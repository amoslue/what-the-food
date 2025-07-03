from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract
import io
import re

# IMPORTANT: Set the path to the tesseract executable if it's not in your PATH
# For Windows example:
# pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

app = FastAPI(
    title="Menu OCR and Structuring Service",
    description="Extracts dish names and descriptions from menu images.",
    version="0.1.0"
)

# --- CORS Configuration (Keep as is) ---
origins = [
    "http://localhost",
    "http://localhost:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# ... (imports and CORS config remain the same) ...

# Remove the 'structure_menu_text' function entirely, or just make it return raw_text if called.
# For simplicity, let's just make the /extract_menu_data/ endpoint return raw text.

# --- Helper Functions (keep preprocess_image_for_ocr and extract_text_with_ocr) ---
def preprocess_image_for_ocr(image_bytes: bytes) -> Image.Image:
    # ... (your updated preprocessing code) ...
    try:
        image = Image.open(io.BytesIO(image_bytes))
        image = image.convert("L")
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(1.8)
        image = image.filter(ImageFilter.SHARPEN)
        image = image.point(lambda x: 0 if x < 180 else 255)
        if image.width < 1500 or image.height < 1500:
             image = image.resize((int(image.width * 1.5), int(image.height * 1.5)), Image.LANCZOS)
        return image
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CouldData not process image: {e}")

def extract_text_with_ocr(image: Image.Image) -> str:
    # ... (your updated OCR text extraction code) ...
    try:
        custom_config = r'--oem 3 --psm 3'
        text = pytesseract.image_to_string(image, lang='eng', config=custom_config)
        return text
    except pytesseract.TesseractError as e:
        raise HTTPException(status_code=500, detail=f"OCR processing failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during OCR: {e}")

# --- API Endpoint (MODIFIED) ---

@app.post("/extract_menu_data/")
async def extract_menu_data(file: UploadFile = File(...)):
    """
    Receives a menu image, performs OCR, and returns the raw extracted text.
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="Uploaded file is not an image.")

    image_bytes = await file.read()
    pil_image = preprocess_image_for_ocr(image_bytes)
    raw_text = extract_text_with_ocr(pil_image)

    # Simplified response: only raw_ocr_output
    return JSONResponse(content={
        "raw_ocr_output": raw_text
    })