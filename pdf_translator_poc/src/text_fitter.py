# text_fitter.py
# Module for advanced text fitting

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

# Character width approximation for quick calculations
# This is a fallback for when proper font metrics are not available
CHAR_WIDTH_RATIO = {
    "default": 0.6,  # Width to height ratio for most Latin characters
    "cjk": 1.0,  # CJK characters are typically square
    "wide": 1.2,  # For wide characters or bold text
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


def estimate_text_width(text, font_name, font_size, pdf_standard_char_width=None):
    """
    Estimate the width of text using PDF-extracted standard character width.

    Args:
        text: Text to measure
        font_name: Font name (not used, kept for compatibility)
        font_size: Font size (not used, kept for compatibility)
        pdf_standard_char_width: Standard character width from first char of this font type

    Returns:
        Estimated width of the text in points
    """
    # Use PDF-extracted standard character width if available
    if pdf_standard_char_width:
        return len(text) * pdf_standard_char_width
    
    # If no PDF metrics available, use a simple fallback based on font size
    # This is much simpler than ReportLab's estimation and more predictable
    fallback_width = font_size * 0.6  # Simple approximation
    return len(text) * fallback_width


def is_cjk_character(char):
    """
    Check if a character is a CJK (Chinese, Japanese, Korean) character.

    Args:
        char: Character to check

    Returns:
        Boolean indicating if the character is CJK
    """
    # Unicode ranges for CJK characters
    cjk_ranges = [
        (0x4E00, 0x9FFF),  # CJK Unified Ideographs
        (0x3040, 0x309F),  # Hiragana
        (0x30A0, 0x30FF),  # Katakana
        (0x3400, 0x4DBF),  # CJK Unified Ideographs Extension A
        (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
        (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
        (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
        (0xF900, 0xFAFF),  # CJK Compatibility Ideographs
        (0x3300, 0x33FF),  # CJK Compatibility
        (0x3200, 0x32FF),  # Enclosed CJK Letters and Months
        (0xAC00, 0xD7AF),  # Hangul Syllables (Korean)
    ]

    code_point = ord(char)
    for start, end in cjk_ranges:
        if start <= code_point <= end:
            return True
    return False


def contains_vietnamese_diacritics(text):
    """
    Check if text contains Vietnamese diacritics.

    Args:
        text: Text to check

    Returns:
        Boolean indicating if the text contains Vietnamese diacritics
    """
    # Common Vietnamese diacritics
    vietnamese_pattern = re.compile(
        r"[\u00C0-\u00C3\u00C8-\u00CA\u00CC\u00CD\u00D2-\u00D5\u00D9\u00DA"
        r"\u00E0-\u00E3\u00E8-\u00EA\u00EC\u00ED\u00F2-\u00F5\u00F9\u00FA"
        r"\u0102\u0103\u0110\u0111\u0128\u0129\u0168\u0169\u01A0\u01A1\u01AF\u01B0"
        r"\u1EA0-\u1EF9]"
    )
    return bool(vietnamese_pattern.search(text))


def split_into_words(text):
    """
    Split text into words, handling both whitespace and non-whitespace languages.

    Args:
        text: Text to split

    Returns:
        List of words
    """
    # For languages with explicit word boundaries (Latin, Cyrillic, etc.)
    if re.search(r"[\u0000-\u007F\u0080-\u024F\u0400-\u04FF\u0500-\u052F]", text):
        return text.split()
    else:
        # For CJK and other languages without explicit word boundaries
        # (this is simplified - in real implementation you'd want more sophisticated logic)
        return [char for char in text]


def calculate_max_chars_per_line(available_width, font_name, font_size):
    """
    Calculate the maximum number of characters that can fit in a line
    
    Args:
        available_width: Available width in points
        font_name: Font name for character width calculation
        font_size: Font size in points
        
    Returns:
        Maximum number of characters that fit in the available width
    """
    try:
        # Sample multiple characters including Vietnamese for more accuracy
        sample_chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789 .,!?ăâêôơưđàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
        total_width = estimate_text_width(sample_chars, font_name, font_size)
        
        if total_width > 0:
            # Calculate accurate average character width
            avg_char_width = total_width / len(sample_chars)
        else:
            # Fallback: use font size ratio approximation
            avg_char_width = font_size * CHAR_WIDTH_RATIO.get("default", 0.6)
        
        # Calculate maximum characters with improved safety margin
        # Use 96% of available width for better utilization
        max_chars = int((available_width * 0.99) / avg_char_width)
        
        # Ensure minimum of 5 characters per line
        max_chars = max(5, max_chars)
        
        logger.debug(f"Char calculation: max_chars={max_chars} (width: {available_width:.1f}pt, avg_char_width: {avg_char_width:.2f}pt)")
        return max_chars
        
    except Exception as e:
        logger.warning(f"Error calculating character width, using fallback: {e}")
        # Fallback calculation based on typical character width
        fallback_chars = int(available_width / (font_size * 0.6))
        return max(5, fallback_chars)


def optimize_text_redistribution(lines, available_width, font_size, font_name, pdf_standard_char_width=None):
    """
    Optimize text redistribution across lines to improve space utilization.
    
    Args:
        lines: List of text lines to optimize
        available_width: Available width in points
        font_size: Font size
        font_name: Font name
        pdf_standard_char_width: Standard character width from PDF
    
    Returns:
        Optimized list of lines or None if no improvement possible
    """
    if len(lines) < 2:
        return None
    
    # Analyze current utilization
    utilizations = []
    for line in lines:
        line_width = estimate_text_width(line, font_name, font_size, pdf_standard_char_width)
        utilization = (line_width / available_width) * 100
        utilizations.append(utilization)
    
    # Check if redistribution is beneficial
    min_util = min(utilizations)
    max_util = max(utilizations)
    
    # Only optimize if there's significant imbalance (>20% difference)
    if max_util - min_util < 20:
        return None
    
    # Find underutilized lines (< 80%)
    underutilized_lines = [i for i, util in enumerate(utilizations) if util < 80]
    if not underutilized_lines:
        return None
    
    logger.info(f"Redistributing text - min util: {min_util:.1f}%, max util: {max_util:.1f}%")
    
    # Combine all words and redistribute
    all_words = []
    for line in lines:
        all_words.extend(line.split())
    
    # Redistribute words more evenly
    optimized_lines = []
    current_line = ""
    safety_width = available_width * 0.96
    
    for word in all_words:
        test_line = current_line + (" " if current_line else "") + word
        test_width = estimate_text_width(test_line, font_name, font_size, pdf_standard_char_width)
        
        if test_width <= safety_width:
            current_line = test_line
        else:
            if current_line:
                optimized_lines.append(current_line)
                current_line = word
            else:
                # Single word too long, add it anyway
                optimized_lines.append(word)
                current_line = ""
    
    if current_line:
        optimized_lines.append(current_line)
    
    # Only return if we have the same number of lines (or fewer)
    if len(optimized_lines) <= len(lines):
        # Log improved utilization
        new_utilizations = []
        for line in optimized_lines:
            line_width = estimate_text_width(line, font_name, font_size, pdf_standard_char_width)
            utilization = (line_width / available_width) * 100
            new_utilizations.append(utilization)
        
        new_min = min(new_utilizations)
        new_max = max(new_utilizations)
        logger.info(f"Redistribution result - min util: {new_min:.1f}%, max util: {new_max:.1f}%")
        
        # Only return if utilization improved
        if new_min > min_util:
            return optimized_lines
    
    return None


# Function to wrap text into a fixed number of lines using precise width-based calculations
def wrap_text(text, available_width, max_lines, font_size, font_name="Helvetica", pdf_standard_char_width=None):
    """
    Wraps text to fit within available width and maximum lines using PDF-extracted character widths.
    This approach uses the standard character width (first character) from the PDF for consistent accuracy.

    Args:
        text: Text to wrap
        available_width: Available width in points
        max_lines: Maximum number of lines
        font_size: Font size
        font_name: Font name
        pdf_standard_char_width: Standard character width from first char of this font type

    Returns:
        TextFittingResult object with wrapped text
    """
    if not text:
        return TextFittingResult("", font_size, [], False, "precise_wrap")

    source = "PDF-extracted" if pdf_standard_char_width else "fallback"
    if not pdf_standard_char_width:
        logger.warning(f"Width wrapping ({source}): available_width={available_width:.1f}pt, max_lines={max_lines}, NO PDF METRICS AVAILABLE")
    else:
        logger.info(f"Width wrapping ({source}): available_width={available_width:.1f}pt, max_lines={max_lines}, standard_char_width={pdf_standard_char_width:.3f}")
        logger.info(f"  Expected chars per line (99% margin): {(available_width * 0.99) / pdf_standard_char_width:.1f}")

    # Split into words for proper word boundary handling
    words = text.split()
    if not words:
        return TextFittingResult("", font_size, [], False, "precise_wrap")

    lines = []
    current_line = ""
    is_truncated = False

    for word in words:
        # Test if adding this word would exceed available width
        test_line = current_line + (" " if current_line else "") + word
        test_width = estimate_text_width(test_line, font_name, font_size, pdf_standard_char_width)
        
        # Use 96% of available width for better utilization (was 92%)
        safety_width = available_width * 0.99
        if test_width <= safety_width:
            # Word fits, add it to current line
            current_line = test_line
        else:
            # Word doesn't fit, start a new line
            if current_line:  # Save current line if it has content
                actual_width = estimate_text_width(current_line, font_name, font_size, pdf_standard_char_width)
                space_left = available_width - actual_width
                utilization = (actual_width / available_width) * 100
                
                # Check for low utilization (but not on the last line) - lowered threshold for better packing
                will_be_last_line = (len(lines) + 1 == max_lines)
                if not will_be_last_line and utilization < 85:
                    logger.warning(f"  Line {len(lines)+1}: '{current_line}' ({len(current_line)} chars, {actual_width:.1f}pt / {available_width:.1f}pt = {utilization:.1f}% - LOW UTILIZATION)")
                else:
                    logger.info(f"  Line {len(lines)+1}: '{current_line}' ({len(current_line)} chars, {actual_width:.1f}pt / {available_width:.1f}pt = {utilization:.1f}%)")
                
                lines.append(current_line)
                current_line = word
                
                # Check if we've reached max lines
                if len(lines) >= max_lines:
                    is_truncated = True
                    break
            else:
                # Single word is too long for the line, try to break it
                if len(word) > 1:
                    # Try to break the word
                    broken_part = break_long_word(word, available_width, font_size, font_name, pdf_standard_char_width)
                    if broken_part:
                        lines.append(broken_part)
                        # Continue with the rest of the word
                        remaining = word[len(broken_part.rstrip('-')):]
                        current_line = remaining
                    else:
                        current_line = word
                else:
                    current_line = word
    
    # Add the last line if it has content and we haven't exceeded max lines
    if current_line and len(lines) < max_lines:
        actual_width = estimate_text_width(current_line, font_name, font_size, pdf_standard_char_width)
        space_left = available_width - actual_width
        utilization = (actual_width / available_width) * 100
        
        # Check if this is the last line (don't report poor utilization for last lines)
        is_last_line = (len(lines) + 1 == max_lines) or (len(current_line.strip()) < len(text.split()[-1]) + 10)
        if is_last_line:
            logger.info(f"  Line {len(lines)+1} (LAST): '{current_line}' ({len(current_line)} chars, {utilization:.1f}%)")
        elif utilization < 85:
            logger.warning(f"  Line {len(lines)+1}: '{current_line}' ({len(current_line)} chars, {actual_width:.1f}pt / {available_width:.1f}pt = {utilization:.1f}% - LOW UTILIZATION)")
        else:
            logger.info(f"  Line {len(lines)+1}: '{current_line}' ({len(current_line)} chars, {actual_width:.1f}pt / {available_width:.1f}pt = {utilization:.1f}%)")
        
        lines.append(current_line)
    elif current_line and len(lines) >= max_lines:
        # We have content but exceeded max lines
        is_truncated = True

    # If no lines were created (edge case), add the original text
    if not lines and text:
        lines.append(text)

    fitted_text = "\n".join(lines)
    
    # Apply redistribution optimization if we have underutilized lines
    if len(lines) > 1 and not is_truncated:
        optimized_lines = optimize_text_redistribution(lines, available_width, font_size, font_name, pdf_standard_char_width)
        if optimized_lines:
            lines = optimized_lines
            fitted_text = "\n".join(lines)
            logger.info("Applied text redistribution optimization")
    
    logger.info(f"Wrapping result: {len(lines)} lines, truncated={is_truncated}")

    return TextFittingResult(fitted_text, font_size, lines, is_truncated, "precise_wrap")


# Function to handle long words using character-based calculations
def break_long_word(word, available_width, font_size, font_name, pdf_standard_char_width=None):
    """
    Break a long word into parts that can fit within available width using PDF-extracted character widths.

    Args:
        word: Long word to break
        available_width: Available width in points
        font_size: Font size
        font_name: Font name
        pdf_standard_char_width: Standard character width from PDF

    Returns:
        Portion of the word that fits, or None if not breakable
    """
    if len(word) <= 1:
        return None

    # Calculate max characters that can fit using PDF metrics if available
    if pdf_standard_char_width:
        max_chars = int((available_width * 0.96) / pdf_standard_char_width)
    else:
        max_chars = calculate_max_chars_per_line(available_width, font_name, font_size)
    
    # Reserve 1 character for the hyphen
    max_word_chars = max_chars - 1
    
    if max_word_chars <= 0:
        return word[0] if len(word) > 0 else None
    
    # If word fits within character limit, break it there
    if len(word) > max_word_chars:
        return word[:max_word_chars] + "-"
    
    # Word doesn't need breaking
    return None


# Function removed as it's no longer needed with the new fitting approach


def process_paragraphs(paragraphs, line_height_ratio=1.2):
    """
    Process translated paragraphs and fit them to their original bounds.
    Uses paragraph metadata (num_lines) to determine fitting strategy.

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

        # Calculate width and height from bounding box if not explicitly provided
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

        # Skip empty paragraphs but ensure they have fitting fields
        if not text or not width or not height:
            processed_paragraph["fitted_lines"] = []
            processed_paragraph["fit_method"] = "not_fitted"
            processed_paragraph["scaled_font_size"] = font_size
            processed_paragraphs.append(processed_paragraph)
            continue

        # Get number of lines from metadata - this is now required
        num_lines = paragraph.get("num_lines", 1)  # Default to 1 if not specified

        # Debug output to check parameters
        logger.debug(
            f"Processing paragraph: text={text[:20]}..., width={width}, height={height}, font_size={font_size}, num_lines={num_lines}"
        )

        # Get PDF-extracted font metrics for this paragraph
        font_metrics = paragraph.get("font_metrics", None)
        
        # Fit text to bounds using the paragraph's line count metadata and PDF metrics
        fitting_result = fit_text_to_bounds(
            text,
            width,
            height,
            font_size,
            font_name,
            line_height_ratio=line_height_ratio,
            num_lines=num_lines,
            font_metrics=font_metrics,
        )

        logger.debug(
            f"Fitting result: method={fitting_result.fit_method}, lines={len(fitting_result.lines)}"
        )

        # Update paragraph with fitted text and metadata
        processed_paragraph["text"] = fitting_result.fitted_text
        processed_paragraph["fitted_lines"] = fitting_result.lines
        processed_paragraph["fit_method"] = fitting_result.fit_method

        # Include the font size (now kept at original size)
        processed_paragraph["scaled_font_size"] = fitting_result.scaled_font_size

        if fitting_result.is_truncated:
            processed_paragraph["is_truncated"] = True

        processed_paragraphs.append(processed_paragraph)

    return processed_paragraphs


def fit_text_to_bounds(
    text,
    available_width,
    available_height,
    font_size,
    font_name="Helvetica",
    min_font_size=None,
    line_height_ratio=1.2,
    num_lines=None,
    font_metrics=None,
):
    """
    Simplified text fitting strategy based on paragraph metadata's num_lines using PDF metrics.

    Args:
        text: Text to fit
        available_width: Available width in points
        available_height: Available height in points
        font_size: Original font size
        font_name: Font name
        min_font_size: Minimum allowable font size (unused in simplified approach)
        line_height_ratio: Line height as a ratio of font size
        num_lines: Number of lines in the paragraph (from extractor metadata)
        font_metrics: PDF-extracted font metrics

    Returns:
        TextFittingResult object with the fitted text
    """
    if not text:
        logger.debug("Empty text, returning empty result")
        return TextFittingResult("", font_size, [], False, "empty")

    # Default to 1 line if no line count metadata
    if not num_lines:
        num_lines = 1

    logger.debug(
        f"Fitting text with {num_lines} lines, width={available_width}, height={available_height}, font_size={font_size}"
    )

    # Single-line paragraph strategy - keep original font size
    if num_lines == 1:
        logger.debug(f"Single line paragraph: {text[:20]}...")
        # Keep original font size
        adjusted_font_size = font_size
        return TextFittingResult(text, adjusted_font_size, [text], False, "single_line")

    # Multi-line paragraph strategy - keep original font size and use wrap_text
    else:
        logger.debug(f"Multi-line paragraph ({num_lines} lines): {text[:20]}...")

        # Keep original font size
        adjusted_font_size = font_size

        # Use our wrap_text function to distribute words across the target number of lines
        # Extract PDF standard character width from font metrics if available
        pdf_standard_char_width = None
        if font_metrics:
            pdf_standard_char_width = font_metrics.get('standard_char_width')
        
        result = wrap_text(
            text, available_width, num_lines, adjusted_font_size, font_name, pdf_standard_char_width
        )

        # Update the result with our adjusted font size
        result.scaled_font_size = adjusted_font_size
        result.fit_method = "multi_line"

        return result
