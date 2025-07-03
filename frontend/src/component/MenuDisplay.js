// src/component/MenuDisplay.js (or MenuDisplay.jsx)

import React from 'react';

// MenuDisplay now accepts 'processedDishes' as a prop
function MenuDisplay({ processedDishes }) {
    // If no processedDishes are provided, don't render anything
    if (!processedDishes || processedDishes.length === 0) {
        return null;
    }

    return (
        <div className="generated-images-section">
            <h2>Generated Food Pictures:</h2> {/* Specific title for this section */}
            <div className="generated-images-grid">
                {processedDishes.map((dish, index) => (
                    <div key={index} className="generated-image-container">
                        <p>{dish.dish_name}</p>
                        {dish.generated_image_base64 ? (
                            <img
                                // THIS IS THE KEY PART for displaying the base64 image
                                src={`data:image/png;base64,${dish.generated_image_base64}`}
                                alt={`Image of ${dish.dish_name}`}
                                className="generated-image" // Apply a class for styling
                                style={{ maxWidth: '300px', height: 'auto', border: '1px solid #eee', borderRadius: '3px' }} // Basic inline styling
                            />
                        ) : (
                            <p>Image not available for {dish.dish_name}</p>
                        )}
                        {/* Optional: Display the image prompt here if desired */}
                        {/* <p className="image-prompt-display">{dish.image_prompt}</p> */}
                    </div>
                ))}
            </div>
        </div>
    );
}

export default MenuDisplay;