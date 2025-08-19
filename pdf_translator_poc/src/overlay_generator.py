# overlay_generator.py
# Module for PDF overlay creation

import os
import logging
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import simpleSplit
from reportlab.lib.colors import Color

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import Google Fonts integration
try:
    from .google_fonts import get_or_download_font
except ImportError:
    try:
        from google_fonts import get_or_download_font
    except ImportError:
        logger.warning("Google Fonts integration not available")
        get_or_download_font = None

# Register fallback fonts for Latin and Japanese text
try:
    pdfmetrics.registerFont(TTFont("NotoSans", "fonts/Noto_Sans/static/NotoSans-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("NotoSerif", "fonts/Noto_Serif/static/NotoSerif-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("NotoSansJP", "fonts/Noto_Sans_JP/static/NotoSansJP-Regular.ttf"))
    pdfmetrics.registerFont(TTFont("NotoSerifJP", "fonts/Noto_Serif_JP/static/NotoSerifJP-Regular.ttf"))
    logger.info("Registered default Noto fonts")
except Exception as e:
    logger.warning(f"Could not register default Noto fonts: {e}")

# Font configurations - Special case fonts for specific languages
FONT_CONFIG = {
    "ja": "NotoSansJP-Regular",  # Japanese translation uses special font
    "vi": "TimesNewRoman-Regular",  # Preferred font for Vietnamese
    "default": None,  # Default uses the original font from the PDF
}

# Available fonts tracking
AVAILABLE_FONTS = {"default": True}

# Dynamic font registry for downloaded Google Fonts
GOOGLE_FONTS_REGISTRY = {}

# Font family mapping - maps common font families to available fonts
FONT_FAMILY_MAPPING = {
    # Sans-serif fonts
    "arial": "sans",
    "helvetica": "sans", 
    "gotham": "sans",
    "calibri": "sans",
    "verdana": "sans",
    "tahoma": "sans",
    "geneva": "sans",
    "lucida": "sans",
    "franklin": "sans",
    "futura": "sans",
    "avenir": "sans",
    "proxima": "sans",
    "lato": "sans",
    "opensans": "sans",
    "roboto": "sans",
    "sourcesans": "sans",
    
    # Serif fonts  
    "times": "serif",
    "timesnewroman": "serif",
    "georgia": "serif",
    "garamond": "serif",
    "minion": "serif",
    "palatino": "serif",
    "bookman": "serif",
    "caslon": "serif",
    "baskerville": "serif",
    "centennial": "serif",
    "utopia": "serif",
    "charter": "serif",
    "crimson": "serif",
    "sourceserif": "serif",
    "ptserif": "serif",
    
    # Monospace fonts (treated as sans for simplicity)
    "courier": "sans",
    "consolas": "sans",
    "monaco": "sans",
    "menlo": "sans",
}

# Available font styles and their corresponding file patterns
FONT_STYLE_MAPPING = {
    "sans": {
        "regular": "fonts/Noto_Sans/static/NotoSans-Regular.ttf",
        "bold": "fonts/Noto_Sans/static/NotoSans-Bold.ttf", 
        "italic": "fonts/Noto_Sans/static/NotoSans-Italic.ttf",
        "bolditalic": "fonts/Noto_Sans/static/NotoSans-BoldItalic.ttf",
    },
    "serif": {
        "regular": "fonts/Noto_Serif/static/NotoSerif-Regular.ttf",
        "bold": "fonts/Noto_Serif/static/NotoSerif-Bold.ttf",
        "italic": "fonts/Noto_Serif/static/NotoSerif-Italic.ttf", 
        "bolditalic": "fonts/Noto_Serif/static/NotoSerif-BoldItalic.ttf",
    },
    "sans_jp": {
        "regular": "fonts/Noto_Sans_JP/static/NotoSansJP-Regular.ttf",
        "bold": "fonts/Noto_Sans_JP/static/NotoSansJP-Bold.ttf",
    },
    "serif_jp": {
        "regular": "fonts/Noto_Serif_JP/static/NotoSerifJP-Regular.ttf", 
        "bold": "fonts/Noto_Serif_JP/static/NotoSerifJP-Bold.ttf",
    }
}


def parse_font_name(font_name):
    """
    Parse a font name to extract family and style information.
    
    Args:
        font_name: Font name from PDF (e.g., "IJCIDQ+Gotham-Book", "Gotham-Italic", "Times-Bold")
    
    Returns:
        tuple: (family, style) where family is the font family and style is the font style
    """
    if not font_name:
        return "helvetica", "regular"
    
    # Remove font subset prefix (e.g., "IJCIDQ+")
    if "+" in font_name:
        font_name = font_name.split("+", 1)[1]
    
    # Handle comma-separated styles (e.g., "Times New Roman,Bold")
    if "," in font_name:
        parts = font_name.split(",")
        base_font = parts[0].strip()
        style_part = parts[1].strip().lower() if len(parts) > 1 else ""
        
        # Determine style from the comma-separated part
        if "bold" in style_part and "italic" in style_part:
            style = "bolditalic"
        elif "bold" in style_part:
            style = "bold"
        elif "italic" in style_part or "oblique" in style_part:
            style = "italic"
        else:
            style = "regular"
        
        # Clean and normalize the base font name
        family = base_font.lower().replace(" ", "").replace("-", "").replace("_", "")
        
    else:
        # Original parsing logic for dash-separated styles
        font_name_lower = font_name.lower()
        style = "regular"
        family = font_name_lower
        
        # Check for style indicators in font name
        style_indicators = {
            "bold": ["bold", "heavy", "black", "extrabold", "semibold", "demibold"],
            "italic": ["italic", "oblique", "slant"],
            "bolditalic": ["bolditalic", "boldobl", "heavyitalic", "blackitalic"]
        }
        
        # First check for bold+italic combinations
        for style_name, indicators in style_indicators.items():
            for indicator in indicators:
                if indicator in font_name_lower:
                    if style_name == "bolditalic":
                        style = "bolditalic"
                        family = font_name_lower.replace(indicator, "").strip("-_ ")
                        break
        
        # If not bold+italic, check for individual styles
        if style == "regular":
            for style_name, indicators in style_indicators.items():
                if style_name == "bolditalic":
                    continue
                for indicator in indicators:
                    if indicator in font_name_lower:
                        style = style_name
                        family = font_name_lower.replace(indicator, "").strip("-_ ")
                        break
                if style != "regular":
                    break
        
        # Clean up family name - remove common suffixes/prefixes and punctuation
        family = family.replace("-", "").replace("_", "").replace(" ", "").strip()
        
        # Remove common style suffixes that might remain (but be careful with "Times New Roman")
        if family != "timesnewroman":  # Don't strip "roman" from "Times New Roman"
            style_suffixes = ["regular", "normal", "roman", "book", "medium", "light", "thin", "mt"]
            for suffix in style_suffixes:
                if family.endswith(suffix):
                    family = family[:-len(suffix)].strip()
                    break
    
    # If family is empty after cleaning, use a default
    if not family:
        family = "helvetica"
    
    logger.debug(f"Parsed font '{font_name}' -> family: '{family}', style: '{style}'")
    return family, style


def get_mapped_font_path(font_family, font_style, target_language="vi"):
    """
    Get the appropriate font path based on font family, style, and target language.
    Also registers the font with ReportLab if not already registered.
    
    Args:
        font_family: Cleaned font family name
        font_style: Font style (regular, bold, italic, bolditalic)  
        target_language: Target language code
    
    Returns:
        tuple: (font_path, font_name) or (None, None) if not found
    """
    # Determine font category based on language and family
    if target_language == "ja":
        # For Japanese, prefer serif for serif families, otherwise sans
        font_category = FONT_FAMILY_MAPPING.get(font_family, "sans")
        if font_category == "serif":
            font_category = "serif_jp"
        else:
            font_category = "sans_jp"
    else:
        # For other languages, use the family mapping
        font_category = FONT_FAMILY_MAPPING.get(font_family, "sans")
    
    # Get available styles for this font category
    available_styles = FONT_STYLE_MAPPING.get(font_category, {})
    
    # Try to get the exact style, fallback to regular
    font_path = available_styles.get(font_style)
    if not font_path:
        font_path = available_styles.get("regular")
        font_style = "regular"  # Update font_style to match what we're actually using
    
    if font_path and os.path.exists(font_path):
        # Generate a unique font name for ReportLab registration
        font_name = f"Mapped_{font_category}_{font_style}_{target_language}"
        
        # Register the font with ReportLab if not already registered
        if font_name not in pdfmetrics.getRegisteredFontNames():
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                logger.info(f"FONT REGISTERED: {font_name} from {font_path}")
            except Exception as e:
                logger.warning(f"Failed to register font {font_name}: {e}")
                return None, None
        
        return font_path, font_name
    
    return None, None


# Function to create white masks over original text
def create_white_mask(c, x, y, width, height, padding=2, debug_outline=False):
    """
    Create an opaque white rectangle over original text with padding

    Args:
        c: ReportLab canvas object
        x, y: Bottom-left corner coordinates
        width, height: Dimensions of the text area
        padding: Extra padding in pixels to ensure complete coverage
        debug_outline: If True, draw red outline around the white mask
    """
    c.setFillColor(Color(1, 1, 1, alpha=1))  # Solid white

    # Expand mask by padding pixels in all directions
    x = x - padding
    y = y - padding
    width = width + (2 * padding)
    height = height + (2 * padding)

    if debug_outline:
        # Draw white mask with red outline for debugging
        c.setStrokeColor(Color(1, 0, 0, alpha=1))  # Red outline
        c.setLineWidth(0.5)  # Slim line
        c.rect(x, y, width, height, fill=1, stroke=1)
    else:
        # Normal white mask without outline
        c.rect(x, y, width, height, fill=1, stroke=0)


def get_font_for_target_language(target_language, original_font):
    """
    Choose the appropriate font based on target language and original font.
    This function prioritizes using the extracted font_name from the PDF to find a matching Google Font.

    Args:
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
        original_font: Font name from original PDF

    Returns:
        Font name to use for the target language
    """
    global AVAILABLE_FONTS, GOOGLE_FONTS_REGISTRY

    logger.debug(
        f"Font selection - Original: '{original_font}', Target language: '{target_language}'"
    )

    # Always try to use Google Fonts first to match the extracted font_name
    if get_or_download_font and original_font:
        try:
            # Create font cache directory if needed
            font_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "fonts_cache"
            )
            os.makedirs(font_dir, exist_ok=True)

            # Generate a clean font name for registration
            clean_name = (
                original_font.lower().replace(" ", "").replace("-", "").replace(",", "")
            )
            registered_name = f"{clean_name.capitalize()}{target_language.upper()}"

            # Check if already registered
            if registered_name in GOOGLE_FONTS_REGISTRY:
                logger.debug(f"Using previously downloaded font: {registered_name}")
                return registered_name

            # Try to get a matching font from Google Fonts with support for the target language
            logger.debug(
                f"Attempting to fetch font similar to '{original_font}' from Google Fonts for {target_language}"
            )
            font_path, font_family_name = get_or_download_font(
                original_font, "regular", font_dir, target_language
            )

            if font_path and os.path.exists(font_path):
                # Create a more descriptive registered name that includes style information
                # Use the original font name to preserve style info for ReportLab registration
                clean_original = (
                    original_font.replace(" ", "").replace(",", "").replace("-", "")
                )
                registered_name = f"{clean_original}_{target_language.upper()}"

                # Register the font if not already registered
                if registered_name not in pdfmetrics.getRegisteredFontNames():
                    pdfmetrics.registerFont(TTFont(registered_name, font_path))
                    GOOGLE_FONTS_REGISTRY[registered_name] = font_path

                    # Store in available fonts for future reference with original font name as key
                    AVAILABLE_FONTS[f"{original_font}_{target_language}"] = (
                        registered_name
                    )

                    # Special tracking for Times-like fonts and Vietnamese
                    if target_language == "vi" and (
                        "times" in original_font.lower()
                        or "serif" in font_family_name.lower()
                    ):
                        # Check if this is bold or italic Times
                        if "bold" in original_font.lower():
                            AVAILABLE_FONTS["times_vi_bold"] = registered_name
                        if "italic" in original_font.lower():
                            AVAILABLE_FONTS["times_vi_italic"] = registered_name
                        AVAILABLE_FONTS["times_vi"] = registered_name
                        AVAILABLE_FONTS["vi"] = registered_name

                    # Special tracking for Japanese fonts
                    if target_language == "ja":
                        AVAILABLE_FONTS["ja"] = True

                    logger.info(
                        f"Dynamically registered font '{registered_name}' for {target_language} from Google Font '{font_family_name}' (original: '{original_font}')"
                    )

                # Return the newly registered font
                return registered_name
            else:
                logger.debug(
                    f"Could not download font '{original_font}' from Google Fonts"
                )
        except Exception as e:
            logger.error(f"Failed to dynamically fetch font '{original_font}': {e}")

    # Fallback to language-specific special handling

    # Use special font for Japanese if Google Fonts failed
    if target_language == "ja" and "ja" in AVAILABLE_FONTS:
        logger.debug(f"Using Japanese-specific font: {FONT_CONFIG['ja']}")
        return FONT_CONFIG["ja"]

    # For Vietnamese, try existing Vietnamese fonts if Google Fonts failed
    if target_language == "vi":
        # Check if we have a Times-compatible Vietnamese font (highest priority)
        if "times_vi" in AVAILABLE_FONTS:
            vi_font = AVAILABLE_FONTS["times_vi"]
            logger.debug(f"Using Times-like Vietnamese font: {vi_font}")
            return vi_font

        # Check if Times-Roman is specially registered with Vietnamese support
        if "TimesNewRomanVN" in AVAILABLE_FONTS:
            logger.debug("Using TimesNewRomanVN with Vietnamese support")
            return "TimesNewRomanVN"

        # Fall back to any Vietnamese font
        if "vi" in AVAILABLE_FONTS:
            vi_font = AVAILABLE_FONTS["vi"]
            logger.debug(f"Using available Vietnamese font: {vi_font}")
            return vi_font

    # Finally fall back to mapped standard font
    mapped_font = map_to_standard_font(original_font)
    logger.debug(f"Using standard mapped font: {mapped_font} (from {original_font})")
    return mapped_font


def map_to_standard_font(original_font):
    """
    Map original PDF font name to a standard font available in ReportLab

    Args:
        original_font: Font name from original PDF

    Returns:
        Standard font name for ReportLab
    """
    if not original_font:
        logger.debug("No original font specified, defaulting to Helvetica")
        return "Helvetica"

    # Strip any suffixes like ",Bold" or "-Bold"
    base_font = original_font.split(",")[0].split("-")[0].lower()

    # Remove spaces for mapping
    base_font_no_spaces = base_font.replace(" ", "")

    logger.debug(
        f"Font mapping - Base font: '{base_font}', No spaces: '{base_font_no_spaces}'"
    )

    # Check for NotoSans availability for Vietnamese text
    if AVAILABLE_FONTS.get("vi") and "NotoSans-Regular" in AVAILABLE_FONTS:
        logger.debug("NotoSans-Regular is available for better Vietnamese support")
        return "NotoSans-Regular"

    # Common font mappings
    font_map = {
        "times": "Times-Roman",
        "timesnewroman": "Times-Roman",
        "times new roman": "Times-Roman",
        "times-roman": "Times-Roman",
        "helvetica": "Helvetica",
        "arial": "Helvetica",
        "courier": "Courier",
        "symbol": "Symbol",
    }

    # Check if it's a bold or italic variant
    is_bold = "bold" in original_font.lower()
    is_italic = any(x in original_font.lower() for x in ["italic", "oblique"])

    # Try to find a match with or without spaces
    base = font_map.get(base_font, None)
    if base is None:
        base = font_map.get(base_font_no_spaces, "Helvetica")

    logger.debug(f"Mapped base: '{base_font}' -> '{base}'")

    # Return mapped font with appropriate style
    result = base
    if is_bold and is_italic:
        result = base + "-BoldOblique"
    elif is_bold:
        result = base + "-Bold"
    elif is_italic:
        result = base + "-Oblique"

    logger.debug(f"Final font with style: '{result}'")
    return result


def get_appropriate_font(paragraph, target_language="vi"):
    """
    Determine appropriate font based on target language and paragraph data.
    Maps fonts with proper style preservation: sans fonts -> NotoSans (with style), serif fonts -> NotoSerif (with style).

    Args:
        paragraph: The paragraph data containing font information
        target_language: Target language code (e.g., 'vi', 'en', 'ja')

    Returns:
        Font name to use for this text
    """
    # Get original font from paragraph (this is the fontname extracted from the PDF)
    original_font = paragraph.get("font_name", "Helvetica")

    logger.debug(
        f"Font selection - Original font: '{original_font}', Target language: {target_language}"
    )

    # Parse the original font name to extract family and style
    font_family, font_style = parse_font_name(original_font)
    logger.info(f"FONT PARSING: '{original_font}' -> family: '{font_family}', style: '{font_style}'")

    # Use the proper font mapping function that handles styles
    font_path, font_name = get_mapped_font_path(font_family, font_style, target_language)
    
    if font_name:
        logger.info(f"FONT SELECTED: {font_name} (path: {font_path})")
        return font_name
    else:
        # Fallback to basic font without style if styled version not found
        logger.warning(f"FONT FALLBACK: No styled font found for {font_family} {font_style}, using basic font")
        return get_fallback_font(target_language)


def get_fallback_font(target_language="vi"):
    """
    Get a reliable fallback font for the target language.
    
    Args:
        target_language: Target language code
        
    Returns:
        Font name that is guaranteed to be available
    """
    if target_language == "ja":
        return "NotoSansJP"
    return "NotoSans"


def register_fonts(font_dir=None):
    """
    Register additional fonts with ReportLab (simplified - no Google Fonts download)

    Args:
        font_dir: Directory containing font files. If None, uses default locations.
    """
    logger.info("Using local Noto fonts only - no Google Fonts download")


def draw_fitted_text(
    c, paragraph, fitted_lines, x, y, font_name, font_size, color, target_language="vi"
):
    """
    Draw fitted text onto a canvas

    Args:
        c: ReportLab canvas
        paragraph: Original paragraph data
        fitted_lines: List of lines from text fitting
        x, y: Base position coordinates
        font_name: Font to use (ignored, will be determined by target language)
        font_size: Font size to use
        color: Text color
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
    """
    try:
        # Get appropriate font for the target language
        font = get_appropriate_font(paragraph, target_language)

        # Log font selection for debugging
        logger.debug(
            f"Original font: {paragraph.get('font_name', 'Unknown')}, Selected font: {font}"
        )

        # Reduce font size by 10%
        adjusted_font_size = font_size * 0.9
        
        # Set the font
        try:
            c.setFont(font, adjusted_font_size)
            logger.debug(f"Using font: {font} with adjusted size: {adjusted_font_size:.1f} (original: {font_size:.1f})")
        except Exception as e:
            # If font setting fails, fall back to Helvetica
            logger.warning(
                f"Font '{font}' not available ({str(e)}), falling back to Helvetica"
            )
            c.setFont("Helvetica", adjusted_font_size)

        # Set color (default to black if not provided)
        if color:
            if isinstance(color[0], list):
                # If we have RGB color components
                c.setFillColorRGB(color[0][0], color[0][1], color[0][2])
            else:
                # If we have grayscale
                c.setFillColorRGB(color[0], color[0], color[0])
        else:
            c.setFillColorRGB(0, 0, 0)  # Default black

        # Calculate line height using adjusted font size
        line_height = adjusted_font_size * 1.2  # Add some leading

        # Draw each line
        for i, line in enumerate(fitted_lines):
            # Position is from bottom, so we start at y and go up for each line
            line_y = y + (len(fitted_lines) - 1 - i) * line_height
            c.drawString(x, line_y, line)

    except Exception as e:
        logger.error(f"Error drawing text: {str(e)}")
        # If all else fails, at least try to render something
        try:
            c.setFont("Helvetica", font_size)
            c.setFillColorRGB(0, 0, 0)  # Black
            c.drawString(x, y, "Text rendering error")
        except:
            pass  # Silently fail if we can't even do that


def generate_overlay(
    paragraphs,
    output_path,
    page_size=(612, 792),
    font_dir=None,
    target_language="vi",
    debug_outline=False,
):
    """
    Generate an overlay PDF with white masks and translated text

    Args:
        paragraphs: List of paragraph objects with translation data
        output_path: Path to save the generated overlay PDF
        page_size: Size of PDF pages as (width, height)
        font_dir: Directory containing font files
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
        debug_outline: If True, draw red outlines around white masks for debugging

    Returns:
        Path to the generated overlay PDF
    """
    try:
        # Register necessary fonts
        register_fonts(font_dir)

        # Create a canvas for PDF generation
        c = canvas.Canvas(output_path, pagesize=page_size)

        # Group paragraphs by page
        pages = {}
        for para in paragraphs:
            page_num = para.get("page_number", 1)
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(para)

        # Process each page
        for page_num in sorted(pages.keys()):
            page_paragraphs = pages[page_num]

            # Process paragraphs on this page
            for para in page_paragraphs:
                # Get paragraph data
                x = para["bounding_box"]["x0"]
                y = para["bounding_box"]["y0"]

                # Calculate width and height from bounding box if not explicitly provided
                width = para.get(
                    "width", para["bounding_box"]["x1"] - para["bounding_box"]["x0"]
                )
                height = para.get(
                    "height", para["bounding_box"]["y1"] - para["bounding_box"]["y0"]
                )

                font_name = para.get("font_name", "Helvetica")
                font_size = para.get("scaled_font_size", para.get("font_size", 10))
                color = para.get("non_stroking_color")

                # Create white mask to cover original text
                create_white_mask(c, x, y, width, height, debug_outline=debug_outline)

                # Draw translated text using fitted lines if available
                if "fitted_lines" in para and para["fitted_lines"]:
                    # Get target language from paragraph if available, otherwise use default
                    lang = para.get("target_language", target_language)
                    
                    # Get appropriate font based on original font and target language
                    selected_font = get_appropriate_font(para, lang)
                    
                    draw_fitted_text(
                        c,
                        para,
                        para["fitted_lines"],
                        x,
                        y,
                        selected_font,
                        font_size,
                        color,
                        target_language=lang,
                    )
                else:
                    logger.warning(
                        f"No fitted lines available for paragraph on page {page_num}"
                    )

            # Finish the current page
            c.showPage()

        # Save the PDF
        c.save()
        logger.info(f"Generated overlay PDF: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error generating overlay: {str(e)}")
        raise


def generate_overlay_from_json(
    json_path, output_path, target_language="vi", page_size=(612, 792), font_dir=None
):
    """
    Generate an overlay PDF from a JSON file containing paragraph data

    Args:
        json_path: Path to JSON file with paragraph data
        output_path: Path to save the generated overlay PDF
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
        page_size: Size of PDF pages as (width, height)
        font_dir: Directory containing font files

    Returns:
        Path to the generated overlay PDF
    """
    import json

    try:
        # Set logging level to debug for this run
        logger.setLevel(logging.DEBUG)

        logger.info(f"Generating overlay from JSON: {json_path}")
        logger.info(f"Target language: {target_language}")

        if font_dir:
            logger.info(f"Using custom font directory: {font_dir}")

        # Load paragraph data from JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Handle different JSON formats
        if "pages" in data:
            # Extract paragraphs from pages
            logger.debug("JSON contains 'pages' key, extracting paragraphs")
            all_paragraphs = []
            for page in data["pages"]:
                page_num = page.get("page_num", 0)
                for para in page.get("paragraphs", []):
                    # Add page_number if not present
                    if "page_number" not in para:
                        para["page_number"] = page_num
                    # Add translated_text as text if not present
                    if "text" not in para and "translated_text" in para:
                        para["text"] = para["translated_text"]
                    all_paragraphs.append(para)
            paragraphs = all_paragraphs
        else:
            # Assume it's a direct list of paragraphs
            logger.debug("JSON assumed to contain paragraphs directly")
            paragraphs = data

        logger.info(f"Processing {len(paragraphs)} paragraphs")

        # Generate overlay
        return generate_overlay(
            paragraphs, output_path, page_size, font_dir, target_language
        )

    except Exception as e:
        logger.error(f"Error generating overlay from JSON: {str(e)}")
        raise


def debug_overlay(paragraphs, output_path, highlight_boxes=False, page_size=(612, 792)):
    """
    Generate a debug overlay that shows bounding boxes and positioning

    Args:
        paragraphs: List of paragraph objects with translation data
        output_path: Path to save the generated debug overlay PDF
        highlight_boxes: Whether to draw colored boxes instead of white masks
        page_size: Size of PDF pages as (width, height)

    Returns:
        Path to the generated debug overlay PDF
    """
    try:
        # Create a canvas for PDF generation
        c = canvas.Canvas(output_path, pagesize=page_size)

        # Group paragraphs by page
        pages = {}
        for para in paragraphs:
            page_num = para.get("page_number", 1)
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(para)

        # Process each page
        for page_num in sorted(pages.keys()):
            page_paragraphs = pages[page_num]

            # Process paragraphs on this page
            for para in page_paragraphs:
                # Get paragraph data
                x = para["bounding_box"]["x0"]
                y = para["bounding_box"]["y0"]

                # Calculate width and height from bounding box if not explicitly provided
                width = para.get(
                    "width", para["bounding_box"]["x1"] - para["bounding_box"]["x0"]
                )
                height = para.get(
                    "height", para["bounding_box"]["y1"] - para["bounding_box"]["y0"]
                )

                if highlight_boxes:
                    # Draw colored box for debugging
                    c.setFillColorRGB(
                        0.9, 0.9, 0.5, alpha=0.3
                    )  # Semi-transparent yellow
                    c.setStrokeColorRGB(1, 0, 0)  # Red outline
                    c.rect(x, y, width, height, fill=1, stroke=1)

                    # Add box coordinates as text
                    c.setFont("Helvetica", 6)
                    c.setFillColorRGB(0, 0, 1)
                    c.drawString(
                        x, y - 8, f"({x:.1f},{y:.1f}) {width:.1f}x{height:.1f}"
                    )
                else:
                    # Create white mask
                    create_white_mask(c, x, y, width, height)

                # Display fit method
                if "fit_method" in para:
                    c.setFont("Helvetica", 6)
                    c.setFillColorRGB(0, 0, 1)
                    c.drawString(x + width + 2, y, f"{para['fit_method']}")

            # Finish the current page
            c.showPage()

        # Save the PDF
        c.save()
        logger.info(f"Generated debug overlay PDF: {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error generating debug overlay: {str(e)}")
        raise


# Main function for standalone testing
if __name__ == "__main__":
    import sys
    import json

    if len(sys.argv) < 3:
        print(
            "Usage: python overlay_generator.py <input_json_path> <output_pdf_path> [font_dir]"
        )
        sys.exit(1)

    json_path = sys.argv[1]
    output_path = sys.argv[2]
    font_dir = sys.argv[3] if len(sys.argv) > 3 else None

    # Load paragraph data from JSON
    with open(json_path, "r", encoding="utf-8") as f:
        paragraphs = json.load(f)

    # Generate overlay
    generate_overlay(paragraphs, output_path, font_dir=font_dir)

    # Also generate a debug overlay
    debug_path = output_path.replace(".pdf", "_debug.pdf")
    debug_overlay(paragraphs, debug_path, highlight_boxes=True)

    print(f"Generated overlay PDF: {output_path}")
    print(f"Generated debug PDF: {debug_path}")
