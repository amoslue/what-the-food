import React, { useState, useRef } from 'react';

function App() {
  const [selectedImage, setSelectedImage] = useState(null);
  const [rawOcrOutput, setRawOcrOutput] = useState(''); // New state for raw OCR text
  const [structuredDishes, setStructuredDishes] = useState([]); // New state for structured data from OCR
  const [generatedImages, setGeneratedImages] = useState([]); // This will eventually store generated food images
  const [isLoading, setIsLoading] = useState(false); // To show loading state
  const [error, setError] = useState(null); // To handle errors

  const fileInputRef = useRef(null);

  const handleImageChange = (event) => {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onloadend = () => {
        setSelectedImage(reader.result); // Set the image preview
      };
      reader.readAsDataURL(file);

      // Now, send the file to the backend
      uploadImageToBackend(file);

    } else {
      setSelectedImage(null);
      setRawOcrOutput('');
      setStructuredDishes([]);
      setGeneratedImages([]);
      setError(null);
    }
  };

  // Function to trigger file input click (for custom button)
  const handleUploadButtonClick = () => {
    fileInputRef.current.click();
  };

  const uploadImageToBackend = async (imageFile) => {
    setIsLoading(true);
    setError(null);
    setRawOcrOutput('');
    setStructuredDishes([]);
    setGeneratedImages([]); // Clear previous results

    const formData = new FormData();
    formData.append("file", imageFile); // 'file' matches the parameter name in your FastAPI endpoint

    try {
      const response = await fetch('http://localhost:8000/extract_menu_data/', {
        method: 'POST',
        body: formData,
        // When using FormData, fetch automatically sets the 'Content-Type' header to 'multipart/form-data'
      });

      if (!response.ok) {
        // Handle HTTP errors (e.g., 400, 500)
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setRawOcrOutput(data.raw_ocr_output);
      setStructuredDishes(data.structured_menu_data);

      // For now, let's just use the structured dish names to display something
      // This will be replaced by actual generated image URLs later
      const mockGenerated = data.structured_menu_data.map(dish => ({
        dishName: dish.name,
        imageUrl: `https://via.placeholder.com/300x200?text=${encodeURIComponent(dish.name)}`
      }));
      setGeneratedImages(mockGenerated);

    } catch (err) {
      console.error("Error uploading image:", err);
      setError(`Failed to process image: ${err.message}`);
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
          capture="environment" // Hint to mobile browsers to prefer camera
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

        <h3>Structured Dishes (from OCR):</h3>
        {structuredDishes.length > 0 ? (
          <ul>
            {structuredDishes.map((dish, index) => (
              <li key={index}>
                <strong>{dish.name}:</strong> {dish.description || "(No description)"}
              </li>
            ))}
          </ul>
        ) : (
          !isLoading && !error && selectedImage && <p>No structured dishes found yet or awaiting upload.</p>
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
          !isLoading && !error && selectedImage && <p className="no-image-placeholder">Images will appear here after generation (currently placeholders).</p>
        )}
      </div>
    </div>
  );
}

export default App;