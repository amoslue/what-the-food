import React, { useState, useRef } from 'react';

function App() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [rawOcrOutput, setRawOcrOutput] = useState('');
  const [structuredDishes, setStructuredDishes] = useState([]); // Now from NLU
  const [nluPrompts, setNluPrompts] = useState([]);
  const [generatedImages, setGeneratedImages] = useState([]); // Will store actual images later
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const fileInputRef = useRef(null);

  const handleImageChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result);
      };
      reader.readAsDataURL(file);

      processMenuImage(file);

    } else {
      setSelectedImage(null);
      setRawOcrOutput('');
      setStructuredDishes([]);
      setNluPrompts([]);
      setGeneratedImages([]);
      setError(null);
    }
  };

  const handleUploadButtonClick = () => {
    fileInputRef.current.click();
  };

  const processMenuImage = async (imageFile) => {
    setIsLoading(true);
    setError(null);
    setRawOcrOutput('');
    setStructuredDishes([]);
    setNluPrompts([]);
    setGeneratedImages([]);

    try {
      // --- Step 1: Call OCR Service to get raw text ---
      const ocrFormData = new FormData();
      ocrFormData.append("file", imageFile);

      const ocrResponse = await fetch('http://localhost:8000/extract_menu_data/', {
        method: 'POST',
        body: ocrFormData,
      });

      if (!ocrResponse.ok) {
        const errorData = await ocrResponse.json();
        throw new Error(errorData.detail || `OCR service error! status: ${ocrResponse.status}`);
      }

      const ocrData = await ocrResponse.json();
      setRawOcrOutput(ocrData.raw_ocr_output);

      // --- Step 2: Call NLU Service with raw OCR text ---
      const nluResponse = await fetch('http://localhost:8001/process_menu_text/', { // Updated endpoint
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ raw_ocr_text: ocrData.raw_ocr_output }), // Send raw text
      });

      if (!nluResponse.ok) {
        const errorData = await nluResponse.json();
        throw new Error(errorData.detail || `NLU service error! status: ${nluResponse.status}`);
      }

      const nluData = await nluResponse.json();
      setStructuredDishes(nluData.structured_menu_data); // Structured data now comes from NLU
      setNluPrompts(nluData.processed_dishes);

      // Use NLU prompts for placeholders
      const mockGenerated = nluData.processed_dishes.map(item => ({
        dishName: item.dish_name,
        imageUrl: `https://via.placeholder.com/300x200?text=${encodeURIComponent(item.dish_name.substring(0, 20) + '...')}` // Placeholder based on dish name
      }));
      setGeneratedImages(mockGenerated);


    } catch (err) {
      console.error("Error processing menu:", err);
      setError(`Failed to process menu: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="App">
      <h1>Menu-to-Picture Generator</h1>

      <div className="upload-section">
        <h2>Upload Your Menu</h2>
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleImageChange}
          className="hidden-file-input"
          ref={fileInputRef}
        />
        <button className="upload-button" onClick={handleUploadButtonClick} disabled={isLoading}>
          {isLoading ? 'Processing...' : 'Upload Menu Image (Camera/Gallery)'}
        </button>

        {selectedImage && (
          <div>
            <h3>Selected Menu Preview:</h3>
            <img src={selectedImage} alt="Selected Menu" className="image-preview" />
          </div>
        )}
      </div>

      <div className="results-section">
        <h2>Processing Results</h2>

        {isLoading && <p>Loading and processing your menu...</p>}
        {error && <p className="error-message">Error: {error}</p>}

        {rawOcrOutput && (
          <div className="ocr-output-section">
            <h3>Raw OCR Output (for Debugging):</h3>
            <pre className="raw-text-display">{rawOcrOutput}</pre>
          </div>
        )}

        <h3>Structured Dishes (from LLM):</h3> {/* Updated label */}
        {structuredDishes.length > 0 ? (
          <ul>
            {structuredDishes.map((dish, index) => (
              <li key={index}>
                <strong>{dish.name}:</strong> {dish.description || "(No description)"}
              </li>
            ))}
          </ul>
        ) : (
          !isLoading && !error && selectedImage && <p>LLM is processing or no structured dishes found.</p>
        )}

        <h3>Generated Image Prompts (from LLM):</h3> {/* Updated label */}
        {nluPrompts.length > 0 ? (
          <ul>
            {nluPrompts.map((item, index) => (
              <li key={index}>
                <strong>{item.dish_name}:</strong> <em>{item.image_prompt}</em>
              </li>
            ))}
          </ul>
        ) : (
          !isLoading && !error && selectedImage && structuredDishes.length > 0 && <p>LLM is processing or no prompts generated.</p>
        )}

        <h2>Generated Food Pictures (Placeholder)</h2>
        {generatedImages.length > 0 ? (
          <div className="generated-images-grid">
            {generatedImages.map((item, index) => (
              <div key={index} className="generated-image-container">
                <p>{item.dishName}</p>
                <img src={item.imageUrl} alt={item.dishName} className="generated-image" />
              </div>
            ))}
          </div>
        ) : (
          !isLoading && !error && selectedImage && nluPrompts.length > 0 && <p className="no-image-placeholder">Images will appear here after generation (currently placeholders).</p>
        )}
      </div>
    </div>
  );
}

export default App;