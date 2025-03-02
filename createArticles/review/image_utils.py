"""
Utility functions for verifying and handling images.
"""

import os
import requests
import urllib.parse

def verify_image_accessibility(image_url: str) -> bool:
    """
    Verify if an image URL is accessible by attempting to fetch it.
    Returns True if the image is accessible, False otherwise.
    """
    try:
        if not image_url or not image_url.strip():
            print("Empty image URL")
            return False
        
        # Clean the URL
        image_url = image_url.strip()
        
        # Add https:// if the URL starts with //
        if image_url.startswith('//'):
            image_url = 'https:' + image_url
            
        # Ensure URL is properly encoded
        parsed = urllib.parse.urlparse(image_url)
        encoded_url = urllib.parse.urlunparse(
            parsed._replace(
                path=urllib.parse.quote(parsed.path),
                query=urllib.parse.quote(parsed.query, safe='=&')
            )
        )
        
        print(f"Checking image URL: {encoded_url}")
        
        # Make request with extended timeout and allow redirects
        response = requests.get(
            encoded_url,
            timeout=15,
            allow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8'
            },
            stream=True  # Don't download the whole image, just headers
        )
        
        # Print response details for debugging
        print(f"Response status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")
        
        # Check status code first (accept 200-299 range)
        if not (200 <= response.status_code < 300):
            print(f"Image URL returned status code {response.status_code}: {encoded_url}")
            return False
            
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        content_length = response.headers.get('content-length')
        
        print(f"Content type: {content_type}")
        print(f"Content length: {content_length}")
        
        # More permissive content type checking
        valid_content_types = ['image', 'application/octet-stream', 'binary/octet-stream']
        
        if not any(t in content_type for t in valid_content_types):
            # If content type check fails, try to check file extension
            file_ext = os.path.splitext(parsed.path)[1].lower()
            valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.svg']
            
            if file_ext not in valid_extensions:
                print(f"URL does not appear to be an image (content-type: {content_type}, extension: {file_ext}): {encoded_url}")
                return False
        
        # Consider it valid if we got this far
        return True
        
    except requests.Timeout:
        print(f"Timeout while accessing image URL: {image_url}")
        return False
    except requests.RequestException as e:
        print(f"Error accessing image URL {image_url}: {str(e)}")
        return False
    except Exception as e:
        print(f"Unexpected error checking image URL {image_url}: {str(e)}")
        return False