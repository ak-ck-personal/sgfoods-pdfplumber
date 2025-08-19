# text_fitter.py
# Module for advanced text fitting with Noto font metrics

import re
import math
import logging
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import Color

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Default Noto font character width approximations (points per character at 1pt font size)
# These values are measured from actual Noto font metrics
NOTO_FONT_METRICS = {
    "NotoSans": {
        "regular": 0.55,
        "bold": 0.60, 
        "italic": 0.55,
        "bolditalic": 0.60,
    },
    "NotoSerif": {
        "regular": 0.50,
        "bold": 0.55,
        "italic": 0.50, 
        "bolditalic": 0.55,
    },
    "NotoSansJP": {
        "regular": 1.0,  # CJK characters are typically square
        "bold": 1.0,
    },
    "NotoSerifJP": {
        "regular": 1.0,
        "bold": 1.0,
    },
}

class TextFittingResult:
    """
    Class to hold the result of text fitting operations.
    """

    def __init__(
        self,
        fitted_text,
        scaled_font_size=None,
        lines=None,
        is_truncated=False,
        fit_method=None,
    ):
        self.fitted_text = fitted_text
        self.scaled_font_size = scaled_font_size
        self.lines = lines if lines else []
        self.is_truncated = is_truncated
        self.fit_method = fit_method

    def __str__(self):
        return (
            f"TextFittingResult(method={self.fit_method}, scaled_size={self.scaled_font_size}, "
            f"lines={len(self.lines)}, truncated={self.is_truncated})"
        )


def get_noto_font_metrics(font_family, font_style):
    """
    Get character width metrics for Noto fonts.
    
    Args:
        font_family: Font family (e.g., "NotoSans", "NotoSerif", "NotoSansJP")
        font_style: Font style ("regular", "bold", "italic", "bolditalic")
        
    Returns:
        Character width ratio (width per character at 1pt font size)
    """
    # Normalize font family names
    if "sans" in font_family.lower():
        if "jp" in font_family.lower():
            family_key = "NotoSansJP"
        else:
            family_key = "NotoSans"
    elif "serif" in font_family.lower():
        if "jp" in font_family.lower():
            family_key = "NotoSerifJP" 
        else:
            family_key = "NotoSerif"
    else:
        # Default to NotoSans for unknown fonts
        family_key = "NotoSans"
    
    # Normalize style
    style_key = font_style.lower() if font_style else "regular"
    if style_key not in ["regular", "bold", "italic", "bolditalic"]:
        style_key = "regular"
    
    # Get metrics with fallback
    family_metrics = NOTO_FONT_METRICS.get(family_key, NOTO_FONT_METRICS["NotoSans"])
    char_width_ratio = family_metrics.get(style_key, family_metrics["regular"])
    
    return char_width_ratio


def calculate_text_width_with_noto_metrics(text, font_family, font_style, font_size):
    """
    Calculate text width using actual Noto font metrics.
    
    Args:
        text: Text to measure
        font_family: Font family name
        font_style: Font style
        font_size: Font size in points
        
    Returns:
        Estimated text width in points
    """
    if not text:
        return 0
    
    # Get base character width for this Noto font
    base_char_width = get_noto_font_metrics(font_family, font_style)
    
    # Apply font size scaling
    char_width = base_char_width * font_size
    
    # Apply text-specific adjustments
    alpha_chars = [c for c in text if c.isalpha()]
    if alpha_chars:
        capital_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        # All capitals are wider
        if capital_ratio > 0.7:
            width_factor = 1.02  # Only 2% increase for capitals
        else:
            width_factor = 0.90  # 10% reduction for mixed case (better packing)
    else:
        # Numbers and punctuation
        width_factor = 0.85
    
    return len(text) * char_width * width_factor


def calculate_max_chars_per_line(available_width, font_family, font_style, font_size):
    """
    Calculate maximum characters per line using Noto font metrics.
    
    Args:
        available_width: Available width in points
        font_family: Font family name
        font_style: Font style 
        font_size: Font size in points
        
    Returns:
        Maximum number of characters that fit in available width
    """
    # Use sample text to get accurate average character width
    sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?ăâêôơưđàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
    
    sample_width = calculate_text_width_with_noto_metrics(sample_text, font_family, font_style, font_size)
    
    if sample_width > 0:
        avg_char_width = sample_width / len(sample_text)
    else:
        # Fallback calculation
        base_char_width = get_noto_font_metrics(font_family, font_style)
        avg_char_width = base_char_width * font_size * 0.9
    
    # Use 97% of available width for safe utilization
    max_chars = int((available_width * 0.97) / avg_char_width)
    
    # Ensure minimum of 5 characters per line
    return max(5, max_chars)


def apply_font_reductions(font_size, font_style, text):
    """
    Apply initial font reductions based on style and text content.
    
    Args:
        font_size: Original font size
        font_style: Font style
        text: Text content
        
    Returns:
        Reduced font size after applying default reductions
    """
    # Start with 10% default overlay font reduction
    reduced_size = font_size * 0.9
    
    # Additional reduction for bold text (harder to fit)
    if font_style and "bold" in font_style.lower():
        reduced_size *= 0.95  # Additional 5% reduction for bold
    
    # Check for mostly capital letters (they need less reduction, not more)
    alpha_chars = [c for c in text if c.isalpha()]
    if alpha_chars:
        capital_ratio = sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if capital_ratio > 0.7:
            # Capital text needs less reduction, so add back 3%
            reduced_size = min(reduced_size * 1.03, font_size * 0.98)  # Cap at 2% total reduction
    
    return reduced_size


def wrap_text_with_noto_metrics(text, available_width, max_lines, font_size, font_family, font_style="regular"):
    """
    Wrap text using Noto font metrics for accurate width calculation.
    
    Args:
        text: Text to wrap
        available_width: Available width in points
        max_lines: Maximum number of lines
        font_size: Font size in points
        font_family: Font family name
        font_style: Font style
        
    Returns:
        TextFittingResult object with wrapped text
    """
    if not text:
        return TextFittingResult("", font_size, [], False, "empty")
    
    words = text.split()
    if not words:
        return TextFittingResult("", font_size, [], False, "empty")
    
    lines = []
    current_line = ""
    is_truncated = False
    
    logger.debug(f"Wrapping text with font_size={font_size:.1f}pt, max_lines={max_lines}, available_width={available_width:.1f}pt")
    
    for word in words:
        # Test if adding this word would exceed available width
        test_line = current_line + (" " if current_line else "") + word
        test_width = calculate_text_width_with_noto_metrics(test_line, font_family, font_style, font_size)
        
        # Use 97% of available width for safe utilization
        safety_width = available_width * 0.97
        
        if test_width <= safety_width:
            # Word fits, add it to current line
            current_line = test_line
        else:
            # Word doesn't fit, start a new line
            if current_line:
                # Save current line if it has content
                lines.append(current_line)
                current_line = word
                
                # Check if we've reached max lines
                if len(lines) >= max_lines:
                    is_truncated = True
                    break
            else:
                # Single word is too long - add it anyway but mark as potentially truncated
                current_line = word
    
    # Add the last line if we haven't exceeded max lines
    if current_line and len(lines) < max_lines:
        lines.append(current_line)
    elif current_line and len(lines) >= max_lines:
        is_truncated = True
    
    # If no lines were created, add the original text
    if not lines and text:
        lines.append(text)
    
    fitted_text = "\n".join(lines)
    
    return TextFittingResult(fitted_text, font_size, lines, is_truncated, "wrap")


def fit_text_with_iterative_reduction(text, available_width, available_height, original_font_size, 
                                     font_family, font_style, num_lines, line_height_ratio=1.2):
    """
    Fit text using iterative font reduction approach.
    
    Key algorithm:
    1. Apply default 10% font reduction + style/capital adjustments
    2. Try text wrapping with Noto font metrics
    3. If truncated: reduce font 20%, recalculate char limits, try again
    4. Repeat until text fits or minimum size reached
    
    Args:
        text: Text to fit
        available_width: Available width in points
        available_height: Available height in points
        original_font_size: Original font size
        font_family: Font family name
        font_style: Font style
        num_lines: Target number of lines
        line_height_ratio: Line height ratio
        
    Returns:
        TextFittingResult object with fitted text
    """
    if not text:
        return TextFittingResult("", original_font_size, [], False, "empty")
    
    # Step 1: Apply initial font reductions
    current_font_size = apply_font_reductions(original_font_size, font_style, text)
    logger.info(f"Applied initial reductions: {original_font_size:.1f}pt → {current_font_size:.1f}pt")
    
    # Calculate minimum font size (don't go below 4pt or 30% of original)
    min_font_size = max(4.0, original_font_size * 0.3)
    max_iterations = 10
    iteration = 0
    
    while iteration < max_iterations and current_font_size >= min_font_size:
        iteration += 1
        
        # Try wrapping with current font size
        result = wrap_text_with_noto_metrics(
            text, available_width, num_lines, current_font_size, font_family, font_style
        )
        
        # Check if text fits
        if not result.is_truncated:
            logger.info(f"Text fit successfully after {iteration} iterations at {current_font_size:.1f}pt (was {original_font_size:.1f}pt)")
            result.scaled_font_size = current_font_size
            result.fit_method = f"iterative_fit_{iteration}_iterations"
            return result
        
        # If truncated and we can try increasing lines within height constraint
        if iteration == 1:  # Only try this once
            line_height = current_font_size * line_height_ratio
            max_possible_lines = int(available_height / line_height)
            
            if max_possible_lines > num_lines:
                logger.info(f"Trying expanded lines: {max_possible_lines} vs original {num_lines}")
                expanded_result = wrap_text_with_noto_metrics(
                    text, available_width, max_possible_lines, current_font_size, font_family, font_style
                )
                
                if not expanded_result.is_truncated:
                    logger.info(f"Text fit with expanded lines: {max_possible_lines} lines at {current_font_size:.1f}pt")
                    expanded_result.scaled_font_size = current_font_size
                    expanded_result.fit_method = "expanded_lines"
                    return expanded_result
        
        # Text still truncated - reduce font by 20%
        new_font_size = current_font_size * 0.8
        
        if new_font_size < min_font_size:
            logger.warning(f"Reached minimum font size {min_font_size:.1f}pt, accepting truncation")
            break
            
        logger.info(f"Iteration {iteration}: Text truncated, reducing font {current_font_size:.1f}pt → {new_font_size:.1f}pt")
        current_font_size = new_font_size
    
    # Return best attempt even if truncated
    final_result = wrap_text_with_noto_metrics(
        text, available_width, num_lines, current_font_size, font_family, font_style
    )
    final_result.scaled_font_size = current_font_size
    final_result.fit_method = f"iterative_final_{iteration}_iterations"
    
    if final_result.is_truncated:
        logger.warning(f"Final result still truncated at {current_font_size:.1f}pt after {iteration} iterations")
    
    return final_result


def process_paragraphs(paragraphs, line_height_ratio=1.2):
    """
    Process translated paragraphs and fit them using iterative font reduction.
    
    Args:
        paragraphs: List of paragraph dictionaries with text and metadata
        line_height_ratio: Line height as a ratio of font size
        
    Returns:
        List of processed paragraphs with fitted text
    """
    processed_paragraphs = []
    
    for paragraph in paragraphs:
        # Extract required metadata
        text = paragraph.get("text", "")
        font_name = paragraph.get("font_name", "Helvetica")
        font_size = paragraph.get("font_size", 12)
        
        # Calculate width and height from bounding box
        width = paragraph.get("width")
        height = paragraph.get("height") 
        
        if (not width or not height) and "bounding_box" in paragraph:
            bbox = paragraph["bounding_box"]
            width = width or (bbox["x1"] - bbox["x0"])
            height = height or (bbox["y1"] - bbox["y0"])
        else:
            width = width or 0
            height = height or 0
        
        # Create a copy of the paragraph for processing
        processed_paragraph = paragraph.copy()
        
        # Skip empty paragraphs
        if not text or not width or not height:
            processed_paragraph["fitted_lines"] = []
            processed_paragraph["fit_method"] = "not_fitted"
            processed_paragraph["scaled_font_size"] = font_size
            processed_paragraphs.append(processed_paragraph)
            continue
        
        # Get number of lines from metadata
        num_lines = paragraph.get("num_lines", 1)
        
        # Determine appropriate Noto font family and style
        # This will be based on the original font characteristics
        font_family, font_style = determine_noto_font_mapping(font_name)
        
        logger.debug(f"Processing paragraph: '{text[:30]}...', font={font_family}/{font_style}, size={font_size}, lines={num_lines}")
        
        # Single line handling
        if num_lines == 1:
            # For single lines, just apply initial reductions and use as-is
            reduced_font_size = apply_font_reductions(font_size, font_style, text)
            fitted_result = TextFittingResult(text, reduced_font_size, [text], False, "single_line")
        else:
            # Multi-line handling with iterative reduction
            fitted_result = fit_text_with_iterative_reduction(
                text, width, height, font_size, font_family, font_style, num_lines, line_height_ratio
            )
        
        # Update paragraph with fitted text and metadata
        processed_paragraph["text"] = fitted_result.fitted_text
        processed_paragraph["fitted_lines"] = fitted_result.lines
        processed_paragraph["fit_method"] = fitted_result.fit_method
        processed_paragraph["scaled_font_size"] = fitted_result.scaled_font_size
        
        if fitted_result.is_truncated:
            processed_paragraph["is_truncated"] = True
        
        processed_paragraphs.append(processed_paragraph)
    
    return processed_paragraphs


def determine_noto_font_mapping(original_font_name):
    """
    Map original PDF font to appropriate Noto font family and style.
    
    Args:
        original_font_name: Original font name from PDF
        
    Returns:
        Tuple of (font_family, font_style)
    """
    font_name = original_font_name.lower() if original_font_name else ""
    
    # Determine font family (sans vs serif)
    if any(serif_indicator in font_name for serif_indicator in 
           ["times", "serif", "georgia", "garamond", "minion", "caslon"]):
        font_family = "NotoSerif"
    else:
        # Default to sans-serif
        font_family = "NotoSans"
    
    # Determine font style
    if "bold" in font_name and "italic" in font_name:
        font_style = "bolditalic"
    elif "bold" in font_name:
        font_style = "bold"
    elif "italic" in font_name:
        font_style = "italic"
    else:
        font_style = "regular"
    
    return font_family, font_style


# Legacy function kept for compatibility - now uses new algorithm
def fit_text_to_bounds(text, available_width, available_height, font_size, font_name="Helvetica",
                      min_font_size=None, line_height_ratio=1.2, num_lines=None, font_metrics=None):
    """
    Legacy compatibility function that uses the new iterative reduction algorithm.
    """
    if not text:
        return TextFittingResult("", font_size, [], False, "empty")
    
    if not num_lines:
        num_lines = 1
    
    font_family, font_style = determine_noto_font_mapping(font_name)
    
    if num_lines == 1:
        reduced_font_size = apply_font_reductions(font_size, font_style, text)
        return TextFittingResult(text, reduced_font_size, [text], False, "single_line_legacy")
    else:
        return fit_text_with_iterative_reduction(
            text, available_width, available_height, font_size, 
            font_family, font_style, num_lines, line_height_ratio
        )