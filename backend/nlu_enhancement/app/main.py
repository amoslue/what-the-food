from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import spacy
import re
# Load SpaCy model
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("SpaCy 'en_core_web_sm' model not found. Running: python -m spacy download en_core_web_sm")
    # This should be handled during environment setup, but useful for quick restarts
    import subprocess
    subprocess.run(["python", "-m", "spacy", "download", "en_core_web_sm"])
    nlp = spacy.load("en_core_web_sm")


app = FastAPI(
    title="NLU and Prompt Engineering Service",
    description="Refines dish descriptions and generates image prompts.",
    version="0.1.0"
)

# --- CORS Configuration ---
origins = [
    "http://localhost",
    "http://localhost:3000", # Your React app's address
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Pydantic Models for Request/Response ---

class DishInput(BaseModel):
    name: str = Field(..., description="Name of the dish")
    description: str = Field(default="", description="Description of the dish")

class DishPrompt(BaseModel):
    dish_name: str = Field(..., description="Original name of the dish")
    image_prompt: str = Field(..., description="Generated text prompt for image generation")
    # Optional: You might want to include extracted keywords for debugging
    # keywords: list[str] = []

class NLUResponse(BaseModel):
    processed_dishes: list[DishPrompt] = Field(..., description="List of dishes with generated image prompts")


# --- Helper Functions for NLU and Prompt Engineering ---

def clean_and_normalize_text(text: str) -> str:
    """Basic text cleaning."""
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text) # Replace multiple spaces with single space
    # Add more cleaning like removing special chars or price info if not already done by OCR
    return text

def extract_keywords(text: str) -> list[str]:
    """
    Uses SpaCy to extract potential keywords (nouns, adjectives) from the text.
    This is a simple approach and can be greatly expanded.
    """
    doc = nlp(text)
    keywords = []
    # Filter for useful POS tags: NOUN, ADJ, VERB (for cooking methods)
    for token in doc:
        if token.pos_ in ["NOUN", "ADJ", "VERB"] and not token.is_stop and not token.is_punct:
            keywords.append(token.lemma_) # Use lemma for consistency (e.g., "grilled" from "grilling")
    return list(set(keywords)) # Return unique keywords


def generate_image_prompt(dish_name: str, dish_description: str, keywords: list[str]) -> str:
    """
    Generates a descriptive prompt for a text-to-image model.
    This is the core "prompt engineering" logic.
    """
    base_prompt = "A highly detailed, photorealistic, gourmet presentation of"
    
    # Prioritize description if available and meaningful
    if dish_description and len(dish_description.split()) > 3: # Check for a meaningful description length
        main_subject = dish_description
    else:
        main_subject = dish_name
        
    # Incorporate keywords for richness
    if keywords:
        keyword_str = ", ".join(keywords)
        main_subject += f", featuring {keyword_str}"
    
    # Add stylistic elements
    style_elements = [
        "restaurant quality",
        "studio lighting",
        "top-down view", # or "close-up", "side view"
        "beautiful food photography",
        "ultra realistic",
        "8k",
        "natural light"
    ]
    
    # Basic cuisine inference (very simplistic)
    cuisine_hints = {
        "taco": "Mexican", "burrito": "Mexican", "nacho": "Mexican",
        "pasta": "Italian", "pizza": "Italian", "lasagna": "Italian",
        "curry": "Indian", "naan": "Indian", "sushi": "Japanese", "ramen": "Japanese",
        "pho": "Vietnamese", "dumpling": "Chinese",
        # Add more mappings
    }
    
    inferred_cuisine = ""
    for keyword, cuisine in cuisine_hints.items():
        if keyword in dish_name.lower() or keyword in dish_description.lower():
            inferred_cuisine = cuisine
            break
            
    if inferred_cuisine:
        base_prompt = f"A highly detailed, photorealistic, {inferred_cuisine} gourmet presentation of"
    
    final_prompt = f"{base_prompt} {main_subject.strip()}. {', '.join(style_elements)}."
    
    # Some cleaning for the prompt
    final_prompt = re.sub(r',(\s*,)+', ',', final_prompt) # Remove double commas
    final_prompt = re.sub(r' +', ' ', final_prompt).strip() # Remove double spaces
    
    return final_prompt

# --- API Endpoint ---

@app.post("/process_dishes_for_prompts/", response_model=NLUResponse)
async def process_dishes_for_prompts(dishes_input: list[DishInput]):
    """
    Receives a list of structured dishes (name, description) and returns
    enhanced data with generated image prompts.
    """
    if not dishes_input:
        raise HTTPException(status_code=400, detail="No dishes provided for processing.")

    processed_dishes_output = []
    for dish in dishes_input:
        cleaned_name = clean_and_normalize_text(dish.name)
        cleaned_description = clean_and_normalize_text(dish.description) if dish.description else ""
        
        # Combine name and description for keyword extraction
        text_for_keywords = f"{cleaned_name} {cleaned_description}".strip()
        keywords = extract_keywords(text_for_keywords)
        
        image_prompt = generate_image_prompt(cleaned_name, cleaned_description, keywords)
        
        processed_dishes_output.append(
            DishPrompt(
                dish_name=dish.name, # Keep original name
                image_prompt=image_prompt
                # keywords=keywords # uncomment to debug keywords
            )
        )
    
    return NLUResponse(processed_dishes=processed_dishes_output)

# --- To run the application ---
# From the `nlu_description_enhancement` directory (the one containing app/):
# uvicorn app.main:app --reload --port 8001
# Note: Using port 8001 to avoid conflict with the OCR service on 8000