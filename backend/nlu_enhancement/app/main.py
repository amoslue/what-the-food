import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import openai
import json
import re # To parse JSON string from LLM

# Load environment variables from .env file
load_dotenv()

# Configure OpenAI API key
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY not found in environment variables. Please set it in a .env file.")

openai.api_key = OPENAI_API_KEY

# Initialize FastAPI app
app = FastAPI(
    title="AI-Powered NLU and Prompt Engineering Service",
    description="Uses an LLM to structure menu text and generate image prompts.",
    version="0.2.0"
)

# --- CORS Configuration (Keep as is) ---
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

class RawTextRequest(BaseModel):
    raw_ocr_text: str = Field(..., description="Raw text extracted by OCR from the menu image.")

class DishStructured(BaseModel):
    name: str = Field(..., description="Name of the dish")
    description: str = Field(default="", description="Description of the dish, if available")
    # You might also want to include price here if the LLM can extract it
    # price: str = Field(default="", description="Price of the dish, if available")

class DishPrompt(BaseModel):
    dish_name: str = Field(..., description="Original name of the dish")
    image_prompt: str = Field(..., description="Generated text prompt for image generation")

class NLUResponse(BaseModel):
    structured_menu_data: list[DishStructured] = Field(..., description="List of dishes with names and descriptions extracted by LLM.")
    processed_dishes: list[DishPrompt] = Field(..., description="List of dishes with generated image prompts.")

# --- LLM Helper Function ---

async def call_llm(system_prompt: str, user_prompt: str):
    """
    Generic function to call the OpenAI LLM.
    """
    try:
        client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY) # Use AsyncOpenAI for async FastAPI endpoint
        chat_completion = await client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1, # Instructs model to return JSON
        )
        response_content = chat_completion.choices[0].message.content
        response_content= re.sub(r"^```(?:json)?\s*", "", response_content.strip())
        response_content = re.sub(r"\s*```$", "", response_content.strip())
        print("llm response", response_content)

        return json.loads(response_content)
 
    except openai.APIError as e:
        raise HTTPException(status_code=e.status_code, detail=f"OpenAI API Error: {e.message}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred with LLM call: {e}")

# --- LLM Specific Prompting Functions ---

async def extract_and_structure_dishes_with_llm(raw_text: str) -> list[DishStructured]:
    """
    Uses LLM to extract dish names and descriptions from raw OCR text.
    """
    system_prompt = """
    You are an AI assistant specialized in parsing restaurant menus.
    Your primary task is to **comprehensively extract ALL distinct dish names and their corresponding descriptions** from the provided raw menu text.

    **Instructions for Extraction:**
    1.  **Scan the entire provided text meticulously.** Do not stop after finding the first few dishes.
    2.  Identify every main dish, appetizer, dessert, and drink item that typically appears on a menu.
    3.  For each identified dish, extract its exact name.
    4.  If a description is present for the dish, extract its full description. If no explicit description is available, leave the description field empty ("").
    5.  **Crucially, ignore prices, section headers (e.g., "Appetizers", "Mains", "Desserts"), restaurant contact information, addresses, phone numbers, website URLs, or any other irrelevant boilerplate text.** Focus exclusively on dish entries.
    6.  Avoid including any introductory or concluding remarks, just the JSON.

    **Output Format (CRITICAL):**
    You MUST respond with a JSON object that contains a key 'dishes', which is a list of objects. Each object in the array MUST have 'name' and 'description' keys.
    **Example Output (Illustrative - ensure you extract ALL applicable dishes from the input):**
    ```json

    Example:
    {
    "dishes": [
        {"name": "Spicy Arrabbiata Pasta", "description": "..."},
        {"name": "Classic Cheeseburger", "description": "..."}
    ]
    } 
    ```
    """

   
    user_prompt = f"Raw Menu Text:\n{raw_text}"
    
    try:
        llm_response = await call_llm(system_prompt, user_prompt)
        dishes = llm_response["dishes"]
        print("type returned? ", type(llm_response))

        # --- NEW ROBUSTNESS CHECK ---
        # If the LLM returns a dictionary instead of a list (common error for single items)
        if isinstance(dishes, dict):
            # Try to infer if it's a single dish and wrap it in a list
            if "name" in dishes and "description" in dishes:
                dishes = [dishes]
            else:
                # If it's a dict but doesn't look like a dish, it's still an unexpected format
                raise ValueError(f"LLM returned a single object that does not match expected dish structure: {llm_response}")

        if not isinstance(dishes, list):
            raise ValueError("LLM did not return a JSON array after correction attempt.")
        # --- END NEW ROBUSTNESS CHECK ---
        
        structured_dishes = []
        for item in dishes:
            if not isinstance(item, dict) or "name" not in item:
                # Provide more context in the error
                raise ValueError(f"LLM returned an invalid dish item (missing 'name' or not an object): {item}")
            # Ensure description is always present, even if LLM omitted it
            structured_dishes.append(DishStructured(name=item["name"], description=item.get("description", "")))
        print(structured_dishes)

        return structured_dishes

    except ValueError as e:
        # Re-raise with more specific context if needed, or handle
        raise HTTPException(status_code=500, detail=f"Error parsing LLM structured output: {e}")
    # Other exceptions from call_llm are already handled within call_llm itself

async def generate_prompts_with_llm(structured_dishes: list[DishStructured]) -> list[DishPrompt]:
    # This function's parsing is likely fine if the input `structured_dishes` is correct.
    # We still keep a similar validation for its output just in case.
    dishes_text = "\n".join([f"- {d.name}: {d.description}" if d.description else f"- {d.name}" for d in structured_dishes])

    system_prompt = """
    You are an AI assistant specializing in crafting vivid, photorealistic image generation prompts for food dishes.
    For each dish provided, generate a single, highly descriptive prompt suitable for a text-to-image AI model (e.g., Midjourney, Stable Diffusion).
    Focus on ingredients, cooking style, presentation, and photographic qualities.
    Include terms like "gourmet presentation", "photorealistic", "studio lighting", "top-down view", "close-up", "detailed", "8k", "food photography".
    Infer cuisine style if possible.
    
    CRITICAL: You MUST output a JSON array of objects, where each object has 'dish_name' (original name) and 'image_prompt' keys.
    Even if there is only one prompt, it MUST be wrapped in a JSON array.

    Example Format:
    [
        {"dish_name": "Margherita Pizza", "image_prompt": "A highly detailed, photorealistic image of a classic Neapolitan Margherita Pizza, vibrant red tomato sauce, melted mozzarella cheese, fresh green basil leaves, golden crust, rustic wooden table, soft studio lighting, top-down view, 8k, food photography."},
        {"dish_name": "Spicy Chicken Tacos", "image_prompt": "A close-up, photorealistic image of three gourmet Spicy Chicken Tacos, grilled marinated chicken, fresh cilantro, diced red onions, a drizzle of lime crema, served on a dark slate board, shallow depth of field, natural light, 8k, food photography."}
    ]
    """
    user_prompt = f"Dishes to generate prompts for:\n{dishes_text}"

    try:
        llm_response = await call_llm(system_prompt, user_prompt)
        
        # --- NEW ROBUSTNESS CHECK ---
        # If the LLM returns a dictionary instead of a list
        if isinstance(llm_response, dict):
            # Try to infer if it's a single prompt and wrap it in a list
            if "dish_name" in llm_response and "image_prompt" in llm_response:
                llm_response = [llm_response]
            else:
                raise ValueError(f"LLM returned a single object that does not match expected prompt structure: {llm_response}")

        if not isinstance(llm_response, list):
            raise ValueError("LLM did not return a JSON array after correction attempt.")
        # --- END NEW ROBUSTNESS CHECK ---

        generated_prompts = []
        for item in llm_response:
            if not isinstance(item, dict) or "dish_name" not in item or "image_prompt" not in item:
                raise ValueError(f"LLM returned an invalid prompt item (missing 'dish_name' or 'image_prompt' or not an object): {item}")
            generated_prompts.append(DishPrompt(dish_name=item["dish_name"], image_prompt=item["image_prompt"]))
        return generated_prompts
    except ValueError as e:
        raise HTTPException(status_code=500, detail=f"Error parsing LLM prompt output: {e}")

# --- API Endpoint ---

@app.post("/process_menu_text/", response_model=NLUResponse)
async def process_menu_text(request: RawTextRequest):
    """
    Receives raw OCR text, uses an LLM to structure it, and then
    generates detailed image prompts for each dish.
    """
    print("enter process menu endpoint")
    # Step 1: Structure the raw text into dishes using LLM
    structured_dishes = await extract_and_structure_dishes_with_llm(request.raw_ocr_text)

    # Step 2: Generate image prompts for these structured dishes using LLM
    processed_prompts = await generate_prompts_with_llm(structured_dishes)

    return NLUResponse(
        structured_menu_data=structured_dishes,
        processed_dishes=processed_prompts
    )

# --- To run the application ---
# From the `nlu_description_enhancement` directory:
# uvicorn app.main:app --reload --port 8001