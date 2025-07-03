# remote_image_generator/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from diffusers import AutoPipelineForText2Image
import torch
from PIL import Image
import io
import base64
import os
import asyncio

# --- Configuration ---
# Set your chosen model here. This will determine the optimal parameters below.
MODEL_ID = "segmind/SSD-1B" # OR "stabilityai/sdxl-lightning-4step-unet" etc.
# Note: For SDXL models, native resolution is 1024x1024 for best results.
# Lowering it might save VRAM but can reduce quality for models trained on 1024x1024.
# You could add height and width parameters to the request if you want to make them configurable.
DEFAULT_HEIGHT = 1024
DEFAULT_WIDTH = 1024

app = FastAPI(title="Remote Image Generation API")

# Global variable to hold the loaded pipeline
pipeline = None

class ImageGenerationRequest(BaseModel):
    prompt: str
    negative_prompt: str = "" # Optional negative prompt
    # You can add more parameters here if you want your client to control them:
    # num_inference_steps: int = None
    # guidance_scale: float = None
    # height: int = None
    # width: int = None


class ImageGenerationResponse(BaseModel):
    image_base64: str # Returning base64 for simplicity, or could be a URL

@app.on_event("startup")
async def load_model():
    """
    Load the Stable Diffusion model to the GPU when the FastAPI app starts.
    """
    global pipeline
    print(f"Loading model {MODEL_ID} to GPU...")
    try:
        pipeline = AutoPipelineForText2Image.from_pretrained(
            MODEL_ID,
            torch_dtype=torch.float16, # Use float16 for reduced memory usage on GPU
            variant="fp16" # If the model has an fp16 optimized variant
        )
        # Apply a specific scheduler if required by the model.
        # SSD-1B generally works well with default or DPM++ Karras.
        # Lightning models might have specific scheduler recommendations (e.g., EulerDiscreteScheduler).
        # You can try:
        # from diffusers import EulerDiscreteScheduler
        # pipeline.scheduler = EulerDiscreteScheduler.from_config(pipeline.scheduler.config)


        pipeline.to("cuda") # Move the pipeline to the GPU
        
        # Optional: Apply xformers for memory and speed optimization (if installed)
        try:
            import xformers.ops
            pipeline.enable_xformers_memory_efficient_attention()
            print("xformers enabled for memory efficiency.")
        except ImportError:
            print("xformers not installed or failed to import. Running without xformers.")

        print(f"Model {MODEL_ID} loaded to GPU successfully.")
    except Exception as e:
        print(f"Failed to load model: {e}")
        raise RuntimeError(f"Failed to load model {MODEL_ID}: {e}")

@app.post("/generate_image/", response_model=ImageGenerationResponse)
async def generate_image(request: ImageGenerationRequest):
    """
    Generates an image from a prompt using the loaded Stable Diffusion model.
    """
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Image generation model not loaded yet.")

    print(f"Received prompt: '{request.prompt}' for model: {MODEL_ID}")

    # --- Adjust parameters based on MODEL_ID ---
    num_inference_steps = 0
    guidance_scale = 0.0
    height = DEFAULT_HEIGHT
    width = DEFAULT_WIDTH

    if MODEL_ID == "segmind/SSD-1B":
        num_inference_steps = 20 # A good balance for SSD-1B. Some sources suggest 25.
        guidance_scale = 7.0 # Typical for general SDXL models.
        # SSD-1B is often used at 1024x1024, but 768x768 can be faster and still good.
        # height = 768
        # width = 768
    elif "sdxl-lightning-4step" in MODEL_ID: # For 4-step Lightning models
        num_inference_steps = 4
        guidance_scale = 0.0 # Crucial: Lightning/Turbo models typically use 0.0 or very low guidance_scale
    elif "sdxl-lightning-8step" in MODEL_ID: # For 8-step Lightning models
        num_inference_steps = 8
        guidance_scale = 0.0 # Crucial: Lightning/Turbo models typically use 0.0 or very low guidance_scale
    elif "sdxl-turbo" in MODEL_ID: # For Turbo models
        num_inference_steps = 1 # Or 2, no more than 4.
        guidance_scale = 0.0 # Critical for Turbo models
    elif "stable-diffusion-xl-base-1.0" in MODEL_ID: # For full SDXL Base
        num_inference_steps = 30 # Can go from 20-50 depending on desired quality vs speed
        guidance_scale = 7.5 # Common range is 7.0-9.0 for SDXL Base
    else:
        # Fallback for any other model ID or if not explicitly handled
        print(f"Warning: Using default parameters for unknown model ID: {MODEL_ID}")
        num_inference_steps = 25
        guidance_scale = 7.5

    # You could allow the client to override these if they pass them in the request
    # if request.num_inference_steps is not None:
    #     num_inference_steps = request.num_inference_steps
    # if request.guidance_scale is not None:
    #     guidance_scale = request.guidance_scale
    # if request.height is not None:
    #     height = request.height
    # if request.width is not None:
    #     width = request.width


    print(f"Generating with steps={num_inference_steps}, guidance={guidance_scale}, size={width}x{height}")

    try:
        # Generate image
        image = pipeline(
            prompt=request.prompt,
            negative_prompt=request.negative_prompt,
            num_inference_steps=num_inference_steps,
            guidance_scale=guidance_scale,
            height=height, # Pass height
            width=width   # Pass width
        ).images[0]

        # Convert PIL Image to BytesIO and then to Base64
        buffered = io.BytesIO()
        image.save(buffered, format="PNG") # PNG for lossless quality
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")

        print("Image generated and converted to base64.")
        return ImageGenerationResponse(image_base64=img_str)

    except torch.cuda.OutOfMemoryError:
        print(f"GPU out of memory for prompt: '{request.prompt}' with {MODEL_ID} at {width}x{height}. "
              f"Consider reducing resolution or steps, or using a smaller model.")
        raise HTTPException(status_code=507, detail="GPU out of memory. Try a smaller image size or model.")
    except Exception as e:
        print(f"Error during image generation: {e}")
        raise HTTPException(status_code=500, detail=f"Image generation failed: {e}")

# Add a health check endpoint
@app.get("/health")
async def health_check():
    if pipeline is not None:
        return {"status": "ok", "model_loaded": True}
    return {"status": "loading", "model_loaded": False}