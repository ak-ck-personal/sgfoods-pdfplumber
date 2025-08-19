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
    This function now prioritizes using the exact font_name extracted from the PDF.

    Args:
        paragraph: The paragraph data containing font information
        target_language: Target language code (e.g., 'vi', 'en', 'ja')

    Returns:
        Font name to use for this text
    """
    # Get original font from paragraph (this is the fontname extracted from the PDF)
    original_font = paragraph.get("font_name", "Helvetica")

    # Log the original font for debugging
    logger.debug(
        f"Font selection - Extracted font: '{original_font}', Target language: {target_language}"
    )

    # Use the improved font selection logic that prioritizes Google Fonts matching
    font = get_font_for_target_language(target_language, original_font)
    logger.debug(f"Selected font: '{font}' for extracted font '{original_font}'")

    # Verify font exists in ReportLab's registry
    if font not in pdfmetrics.getRegisteredFontNames() and font not in [
        "Helvetica",
        "Times-Roman",
        "Courier",
        "Symbol",
    ]:
        logger.warning(
            f"Font '{font}' not registered with ReportLab, falling back to Helvetica"
        )
        font = "Helvetica"

    return font


def register_fonts(font_dir=None):
    """
    Register additional fonts with ReportLab

    Args:
        font_dir: Directory containing font files. If None, uses default locations.
    """
    global AVAILABLE_FONTS, GOOGLE_FONTS_REGISTRY

    try:
        # Register standard fonts (these are built-in to ReportLab)
        logger.info("Using built-in ReportLab fonts for standard text")

        # Create font cache directory if not provided
        if not font_dir:
            font_dir = os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "fonts_cache"
            )
            os.makedirs(font_dir, exist_ok=True)
            logger.info(f"Created font cache directory: {font_dir}")

        # Try to download and register Times New Roman with Vietnamese support via Google Fonts
        if get_or_download_font:
            logger.info(
                "Attempting to download Times New Roman with Vietnamese support"
            )
            try:
                # Try to get Times New Roman or similar serif font with Vietnamese support
                tnr_path, tnr_name = get_or_download_font(
                    "Times New Roman", "regular", font_dir, "vi"
                )
                if tnr_path and os.path.exists(tnr_path):
                    font_name = "TimesNewRomanVN"
                    pdfmetrics.registerFont(TTFont(font_name, tnr_path))
                    AVAILABLE_FONTS["times_vi"] = font_name
                    AVAILABLE_FONTS["vi"] = font_name
                    GOOGLE_FONTS_REGISTRY[font_name] = tnr_path
                    logger.info(
                        f"Registered Google Font for Vietnamese Times New Roman: {font_name}"
                    )

                    # Note: Font mapping not needed with new approach
                else:
                    logger.warning(
                        "Could not download Times New Roman with Vietnamese support"
                    )

                # Also try to get NotoSerif Vietnamese as a backup
                noto_path, noto_name = get_or_download_font(
                    "Noto Serif", "regular", font_dir, "vi"
                )
                if (
                    noto_path
                    and os.path.exists(noto_path)
                    and not AVAILABLE_FONTS.get("vi")
                ):
                    font_name = "NotoSerifVietnamese"
                    pdfmetrics.registerFont(TTFont(font_name, noto_path))
                    if not AVAILABLE_FONTS.get("times_vi"):
                        AVAILABLE_FONTS["times_vi"] = font_name
                    AVAILABLE_FONTS["vi"] = font_name
                    GOOGLE_FONTS_REGISTRY[font_name] = noto_path
                    logger.info(
                        f"Registered Google Font for Vietnamese Noto Serif: {font_name}"
                    )

                    # Note: Font mapping not needed with new approach

                # Get Japanese font only if target language is Japanese
                if target_language == "ja":
                    ja_path, ja_name = get_or_download_font(
                        "Noto Sans JP", "regular", font_dir, "ja"
                    )
                    if ja_path and os.path.exists(ja_path):
                        font_name = "NotoSansJP-Regular"
                        pdfmetrics.registerFont(TTFont(font_name, ja_path))
                        AVAILABLE_FONTS["ja"] = True
                        GOOGLE_FONTS_REGISTRY[font_name] = ja_path
                        logger.info(f"Registered Google Font for Japanese: {font_name}")
                else:
                    logger.debug(
                        f"Skipping Japanese font download - target language is {target_language}"
                    )
            except Exception as e:
                logger.error(f"Error during font registration: {e}")

        # Register special case fonts from local files if provided
        if os.path.exists(font_dir):
            # Try to register Japanese font from local file only if needed
            if target_language == "ja" and not AVAILABLE_FONTS.get("ja"):
                ja_font_path = os.path.join(font_dir, "NotoSansJP-Regular.ttf")
                if os.path.exists(ja_font_path):
                    try:
                        pdfmetrics.registerFont(
                            TTFont("NotoSansJP-Regular", ja_font_path)
                        )
                        AVAILABLE_FONTS["ja"] = True
                        logger.info("Registered Japanese font: NotoSansJP-Regular")
                    except Exception as e:
                        logger.error(f"Failed to register Japanese font: {e}")
                else:
                    # Try alternative Japanese font name/extension
                    ja_font_path = os.path.join(font_dir, "NotoSansJP-Regular.otf")
                    if os.path.exists(ja_font_path):
                        try:
                            pdfmetrics.registerFont(
                                TTFont("NotoSansJP-Regular", ja_font_path)
                            )
                            AVAILABLE_FONTS["ja"] = True
                            logger.info(
                                "Registered Japanese font: NotoSansJP-Regular (OTF)"
                            )
                        except Exception as e:
                            logger.error(f"Failed to register Japanese font (OTF): {e}")
                    else:
                        logger.warning(f"Japanese font not found at {ja_font_path}")
            else:
                logger.debug(
                    f"Skipping local Japanese font registration - target language is {target_language}"
                )

            # Try to register Times New Roman Vietnamese font from local file if not already loaded
            if not AVAILABLE_FONTS.get("times_vi"):
                times_vn_font_path = os.path.join(font_dir, "TimesNewRomanVN.ttf")
                if os.path.exists(times_vn_font_path):
                    try:
                        pdfmetrics.registerFont(
                            TTFont("TimesNewRomanVN", times_vn_font_path)
                        )
                        AVAILABLE_FONTS["times_vi"] = "TimesNewRomanVN"
                        AVAILABLE_FONTS["vi"] = "TimesNewRomanVN"
                        logger.info(
                            "Registered Times New Roman Vietnamese font from local file"
                        )

                        # Note: Font mapping not needed with new approach
                    except Exception as e:
                        logger.error(
                            f"Failed to register Times New Roman Vietnamese font: {e}"
                        )
                else:
                    logger.warning(
                        f"Times New Roman Vietnamese font not found at {times_vn_font_path}"
                    )

            # Register any additional TTF files in the font directory
            for file in os.listdir(font_dir):
                if (
                    file.endswith(".ttf")
                    and not file.startswith("Noto")
                    and not file.startswith("DejaVu")
                ):
                    try:
                        font_path = os.path.join(font_dir, file)
                        # Extract font name from filename (remove extension)
                        font_name = os.path.splitext(file)[0]

                        # Register the font if not already registered
                        if (
                            font_name not in GOOGLE_FONTS_REGISTRY
                            and font_name not in pdfmetrics.getRegisteredFontNames()
                        ):
                            pdfmetrics.registerFont(TTFont(font_name, font_path))
                            GOOGLE_FONTS_REGISTRY[font_name] = font_path
                            logger.info(f"Registered additional font: {font_name}")
                    except Exception as e:
                        logger.error(f"Failed to register font {file}: {e}")
        else:
            logger.warning(
                "No valid font directory provided, using system defaults only"
            )

    except Exception as e:
        logger.error(f"Error registering fonts: {e}. Using system defaults.")


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
        font_name: Font to use
        font_size: Font size to use
        color: Text color
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
    """
    try:
        # Get appropriate font for the target language, using the original font extracted from PDF
        # Only Japanese gets special handling
        font = get_appropriate_font(paragraph, target_language)

        # Log font selection for debugging
        logger.debug(
            f"Original font: {paragraph.get('font_name', 'Unknown')}, Selected font: {font}"
        )

        # Ensure we use a font that's guaranteed to exist in ReportLab
        try:
            c.setFont(font, font_size)
            logger.debug(f"Using font: {font} for text: {paragraph['text'][:30]}...")
        except Exception as e:
            # If font setting fails, fall back to Helvetica
            logger.warning(
                f"Font '{font}' not available ({str(e)}), falling back to Helvetica"
            )
            c.setFont("Helvetica", font_size)

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

        # Calculate line height
        line_height = font_size * 1.2  # Add some leading

        # Draw each line
        for i, line in enumerate(fitted_lines):
            # Position is from bottom, so we start at y and go up for each line
            line_y = y + (len(fitted_lines) - 1 - i) * line_height
            c.drawString(x, line_y, line)

            # Log the drawn text for debugging
            if i == 0:  # Only log the first line to avoid spam
                logger.debug(f"Drew text with font {font}: {line[:30]}...")

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
                    draw_fitted_text(
                        c,
                        para,
                        para["fitted_lines"],
                        x,
                        y,
                        font_name,
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
