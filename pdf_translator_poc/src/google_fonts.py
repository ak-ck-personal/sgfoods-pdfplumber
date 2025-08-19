#!/usr/bin/env python
# google_fonts.py
# Module for Google Fonts API integration

import os
import json
import urllib.request
import urllib.parse
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Constants
GOOGLE_FONTS_API_URL = "https://www.googleapis.com/webfonts/v1/webfonts"
# Note: In a real-world application, you should use your own API key
# This is a placeholder and would typically be stored securely
# Set to None to disable Google Fonts API calls
GOOGLE_FONTS_API_KEY = None  # Disabled to avoid API errors
FONTS_CACHE_DIR = "fonts_cache"

# Font family mapping for common PDF fonts
PDF_FONT_TO_GOOGLE_FONT = {
    "times": "Times New Roman",
    "timesnewroman": "Times New Roman",
    "times-roman": "Times New Roman",
    "times new roman": "Times New Roman",
    "helvetica": "Roboto",
    "arial": "Roboto",
    "courier": "Courier Prime",
    "symbol": None,  # Special case, no good Google Font equivalent
}

# Font style mapping to Google Fonts CSS v2 API format
STYLE_MAPPING = {
    "regular": "400",
    "normal": "400", 
    "bold": "700",
    "italic": "1,400",  # italic=1, weight=400
    "bolditalic": "1,700",  # italic=1, weight=700
    "bold italic": "1,700",
    "light": "300",
    "medium": "500",
    "semibold": "600",
    "extrabold": "800",
}

# Weight mapping for numeric values
WEIGHT_MAPPING = {
    "100": "100",
    "200": "200", 
    "300": "300",  # Light
    "400": "400",  # Normal/Regular
    "500": "500",  # Medium
    "600": "600",  # Semi-Bold
    "700": "700",  # Bold
    "800": "800",  # Extra-Bold
    "900": "900",  # Black
}


def parse_font_name_and_style(font_name):
    """
    Parse font name to extract family and style information
    
    Args:
        font_name: Font name from PDF (e.g., "Times New Roman,Bold", "Arial-Italic")
        
    Returns:
        Tuple of (family_name, style_specification_for_google_fonts)
        
    Examples:
        "Times New Roman,Bold" -> ("Times New Roman", "700")
        "Arial,Italic" -> ("Arial", "1,400") 
        "Helvetica-BoldItalic" -> ("Helvetica", "1,700")
        "Times New Roman" -> ("Times New Roman", "400")
    """
    if not font_name:
        return "Helvetica", "400"
        
    # Clean up the font name
    font_name = font_name.strip()
    
    # Handle comma-separated style (e.g., "Times New Roman,Bold")
    if "," in font_name:
        family, style = font_name.split(",", 1)
        family = family.strip()
        style = style.strip().lower()
    # Handle dash-separated style (e.g., "Arial-Bold")
    elif "-" in font_name:
        parts = font_name.rsplit("-", 1)
        if len(parts) == 2 and parts[1].lower() in ["bold", "italic", "bolditalic", "light", "medium", "regular"]:
            family, style = parts
            family = family.strip()
            style = style.strip().lower()
        else:
            family = font_name
            style = "regular"
    else:
        family = font_name
        style = "regular"
    
    # Normalize style names
    style = style.replace("bolditalic", "bolditalic").replace("bold italic", "bolditalic")
    
    # Map style to Google Fonts CSS v2 format
    google_fonts_style = STYLE_MAPPING.get(style, "400")  # Default to regular weight
    
    logger.debug(f"Parsed font: '{font_name}' -> family='{family}', style='{style}', google_style='{google_fonts_style}'")
    
    return family, google_fonts_style


def get_font_list():
    """
    Get a list of all available Google Fonts

    Returns:
        List of font families or None if API call fails
    """
    if GOOGLE_FONTS_API_KEY is None:
        logger.debug("Google Fonts API key not configured, skipping font list retrieval")
        return None
        
    try:
        # Build request URL with API key
        params = urllib.parse.urlencode(
            {"key": GOOGLE_FONTS_API_KEY, "sort": "popularity"}
        )
        url = f"{GOOGLE_FONTS_API_URL}?{params}"

        logger.debug(f"Requesting font list from Google Fonts API: {url}")

        # Make API request
        with urllib.request.urlopen(url) as response:
            data = json.loads(response.read().decode())

        # Extract font families
        fonts = data.get("items", [])
        logger.info(f"Retrieved {len(fonts)} fonts from Google Fonts API")
        return fonts

    except Exception as e:
        logger.error(f"Failed to get font list from Google Fonts API: {e}")
        return None


def find_similar_font(font_name):
    """
    Find a similar Google Font based on the extracted PDF font name

    Args:
        font_name: Font name extracted from PDF

    Returns:
        Dictionary with matched font information or None if no match
    """
    try:
        # Clean up font name for matching
        if not font_name:
            logger.warning("No font name provided to match")
            return None

        clean_name = font_name.lower().split(",")[0].split("-")[0].strip()

        # Check direct mapping first
        mapped_name = PDF_FONT_TO_GOOGLE_FONT.get(clean_name.replace(" ", ""))
        if mapped_name:
            logger.debug(f"Found direct mapping from '{clean_name}' to '{mapped_name}'")
            return {"family": mapped_name}

        # Get font list from API
        fonts = get_font_list()
        if not fonts:
            logger.warning("Could not retrieve font list for matching")
            return None

        # Look for exact match first
        for font in fonts:
            if font["family"].lower() == clean_name:
                logger.debug(f"Found exact match for '{clean_name}': {font['family']}")
                return font

        # Look for partial match
        for font in fonts:
            if clean_name in font["family"].lower():
                logger.debug(
                    f"Found partial match for '{clean_name}': {font['family']}"
                )
                return font

        logger.debug(f"No match found for '{clean_name}', using default")
        return None

    except Exception as e:
        logger.error(f"Error finding similar font: {e}")
        return None


def download_font(
    font_family, style_specification="400", subset="vietnamese,latin", font_dir=None
):
    """
    Download a font from Google Fonts using CSS v2 API with proper font variant support

    Args:
        font_family: Font family name (e.g. "Times New Roman", "Arial")
        style_specification: Google Fonts CSS v2 style specification (e.g. "400", "700", "1,400", "1,700")
        subset: Character sets to include
        font_dir: Directory to save font files

    Returns:
        Path to the downloaded font file or None if failed
    """
    try:
        # Create font directory if it doesn't exist
        if not font_dir:
            font_dir = FONTS_CACHE_DIR

        os.makedirs(font_dir, exist_ok=True)

        # Build CSS v1 URL to get TTF files instead of WOFF2
        # Google Fonts CSS v1 API is more reliable for TTF delivery
        family_encoded = font_family.replace(" ", "+")
        
        # Convert style specification to CSS v1 format
        if "," in style_specification:
            # This is an italic style like "1,400" or "1,700"
            italic, weight = style_specification.split(",")
            if italic == "1":
                style_v1 = f"{weight}italic"
            else:
                style_v1 = weight
        else:
            # This is a regular weight like "400" or "700"  
            style_v1 = style_specification
            
        # Use CSS v1 API which is more reliable for TTF files
        css_url = f"https://fonts.googleapis.com/css?family={family_encoded}:{style_v1}&subset={subset}"

        # Use a simple user agent that requests TTF files
        headers = {
            "User-Agent": "python-requests/2.28.1"
        }

        # Get CSS file with font URL
        req = urllib.request.Request(css_url, headers=headers)
        with urllib.request.urlopen(req) as response:
            css = response.read().decode("utf-8")

        # Extract font URL from CSS
        import re

        font_url_match = re.search(r"src: url\((.+?)\)", css)
        if not font_url_match:
            logger.error(f"Could not find font URL in CSS for {font_family}")
            return None

        font_url = font_url_match.group(1)

        # Generate safe filename based on family and style specification  
        safe_family = font_family.replace(" ", "")
        safe_style = style_specification.replace(",", "").replace(" ", "")
        filename = f"{safe_family}-{safe_style}.ttf"
        file_path = os.path.join(font_dir, filename)

        # Download the font file
        logger.info(f"Downloading {font_family} (style: {style_specification}) from {font_url}")
        req = urllib.request.Request(font_url, headers=headers)
        with urllib.request.urlopen(req) as response, open(file_path, "wb") as out_file:
            data = response.read()
            out_file.write(data)

        logger.info(f"Font downloaded to {file_path}")
        return file_path

    except Exception as e:
        logger.error(f"Error downloading font: {e}")
        return None


def get_or_download_font(
    font_name, style="regular", font_dir=None, target_language=None
):
    """
    Get a font similar to the extracted font name, downloading if necessary with proper font variant support

    Args:
        font_name: Font name extracted from PDF (e.g., "Times New Roman,Bold", "Arial,Italic")
        style: Legacy parameter, ignored in favor of parsing font_name
        font_dir: Directory to save font files
        target_language: Target language code (e.g., 'vi', 'ja')

    Returns:
        Tuple of (font_path, font_family_name) or (None, fallback_font_name)
    """
    try:
        # Parse the font name to extract family and style
        parsed_family, style_specification = parse_font_name_and_style(font_name)
        
        logger.debug(f"Parsed font name '{font_name}' -> family='{parsed_family}', style_spec='{style_specification}'")
        
        # Determine the best subset based on target language
        subset = "latin"
        if target_language == "vi":
            subset = "vietnamese,latin"
        elif target_language == "ja":
            subset = "japanese,latin"

        # Find a similar Google Font based on the parsed family name
        similar_font = find_similar_font(parsed_family)

        if similar_font:
            font_family = similar_font["family"]

            # Create safe filename for checking existing downloads
            safe_family = font_family.replace(" ", "")
            safe_style = style_specification.replace(",", "").replace(" ", "")
            filename = f"{safe_family}-{safe_style}.ttf"

            # Check if already downloaded
            if not font_dir:
                font_dir = FONTS_CACHE_DIR

            os.makedirs(font_dir, exist_ok=True)
            file_path = os.path.join(font_dir, filename)

            if os.path.exists(file_path):
                logger.debug(f"Font already downloaded: {file_path}")
                return file_path, font_family

            # Download the font with the specific style
            downloaded_path = download_font(font_family, style_specification, subset, font_dir)
            if downloaded_path:
                return downloaded_path, font_family

        # Return fallback if no font found or download failed
        logger.warning(f"Could not get font for '{font_name}', using fallback")
        return None, "Helvetica"

    except Exception as e:
        logger.error(f"Error getting font: {e}")
        return None, "Helvetica"


# For testing
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        font_name = sys.argv[1]
        style = sys.argv[2] if len(sys.argv) > 2 else "regular"
        target_lang = sys.argv[3] if len(sys.argv) > 3 else "vi"

        logging.getLogger().setLevel(logging.DEBUG)

        print(f"Looking for font similar to: {font_name} ({style}) for {target_lang}")
        path, name = get_or_download_font(font_name, style, target_language=target_lang)

        print(f"Result: {path}, {name}")
    else:
        print("Usage: python google_fonts.py <font_name> [style] [target_language]")
        print("Example: python google_fonts.py 'Times New Roman' regular vi")
