import os
import requests
from PIL import Image
import time

class ImageToTextAgent:
    def __init__(self):
        self.api_key = os.environ.get("OCR_SPACE_API_KEY")
        self.api_url = "https://api.ocr.space/parse/image"
        self.use_tesseract = False
        
        # Try to import pytesseract as fallback
        try:
            import pytesseract
            self.pytesseract = pytesseract
            self.use_tesseract = True
            print("Tesseract OCR available as fallback")
        except ImportError:
            self.pytesseract = None
            print("Tesseract OCR not available (install: pip install pytesseract)")
        
    def extract_text_from_file(self, image_path):
        """Extract text from a local image file with retry and fallback."""
        # Try OCR.space API first (with retries)
        text = self._extract_with_ocr_space(image_path)
        
        # If OCR.space fails and Tesseract is available, use it as fallback
        if not text and self.use_tesseract:
            print("OCR.space failed, trying Tesseract fallback...")
            text = self._extract_with_tesseract(image_path)
        
        return text
    
    def _extract_with_ocr_space(self, image_path, max_retries=3):
        """Extract text using OCR.space API with retries."""
        for attempt in range(max_retries):
            try:
                with open(image_path, 'rb') as f:
                    payload = {
                        'apikey': self.api_key,
                        'language': 'eng',
                        'isOverlayRequired': False,
                        'detectOrientation': True,
                        'scale': True,
                        'OCREngine': 2
                    }
                    files = {'file': f}
                    
                    # Increased timeout to 60 seconds
                    response = requests.post(self.api_url, data=payload, files=files, timeout=60)
                    result = response.json()
                    
                    if result.get('IsErroredOnProcessing'):
                        error_msg = result.get('ErrorMessage', 'Unknown error')
                        print(f"OCR.space Error: {error_msg}")
                        continue
                    
                    text_parts = []
                    for page in result.get('ParsedResults', []):
                        text_parts.append(page.get('ParsedText', ''))
                    
                    extracted_text = '\n'.join(text_parts).strip()
                    
                    if extracted_text:
                        return extracted_text
                    else:
                        print(f"Attempt {attempt + 1}: No text extracted from OCR.space")
                        
            except requests.exceptions.Timeout:
                print(f"Attempt {attempt + 1}: OCR.space timeout")
                time.sleep(2)  # Wait before retry
            except FileNotFoundError:
                print(f"Error: Image file not found: {image_path}")
                return ""
            except Exception as e:
                print(f"Attempt {attempt + 1}: OCR.space error: {e}")
                time.sleep(2)
        
        print("All OCR.space attempts failed")
        return ""
    
    def _extract_with_tesseract(self, image_path):
        """Extract text using local Tesseract OCR as fallback."""
        try:
            img = Image.open(image_path)
            text = self.pytesseract.image_to_string(img)
            extracted_text = text.strip()
            
            if extracted_text:
                print("✓ Text extracted successfully with Tesseract")
                return extracted_text
            else:
                print("Warning: No text extracted with Tesseract")
                return ""
                
        except Exception as e:
            print(f"Tesseract extraction error: {e}")
            return ""
    
    def extract_text_from_url(self, image_url, max_retries=3):
        """Extract text from an image URL with retries."""
        for attempt in range(max_retries):
            try:
                payload = {
                    'apikey': self.api_key,
                    'url': image_url,
                    'language': 'eng',
                    'isOverlayRequired': False,
                    'detectOrientation': True,
                    'scale': True,
                    'OCREngine': 2
                }
                
                response = requests.post(self.api_url, data=payload, timeout=60)
                result = response.json()
                
                if result.get('IsErroredOnProcessing'):
                    error_msg = result.get('ErrorMessage', 'Unknown error')
                    print(f"OCR.space Error: {error_msg}")
                    continue
                
                text_parts = []
                for page in result.get('ParsedResults', []):
                    text_parts.append(page.get('ParsedText', ''))
                
                extracted_text = '\n'.join(text_parts).strip()
                
                if extracted_text:
                    return extracted_text
                    
            except requests.exceptions.Timeout:
                print(f"Attempt {attempt + 1}: OCR.space timeout for URL")
                time.sleep(2)
            except Exception as e:
                print(f"Attempt {attempt + 1}: Error: {e}")
                time.sleep(2)
        
        return ""
