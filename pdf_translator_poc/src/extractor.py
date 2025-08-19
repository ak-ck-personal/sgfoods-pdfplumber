# extractor.py
# Module for PDF text extraction

import pdfplumber
import logging

# Configure logging for debugging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def extract_font_metrics(char_data):
    """
    Extract precise character width measurements from PDF character data.
    
    Args:
        char_data: List of character dictionaries from pdfplumber
        
    Returns:
        Dictionary mapping font variants to their character width metrics
    """
    font_metrics = {}
    
    for char in char_data:
        # Create unique key for font variant (family + size)
        font_name = char.get("fontname", "Unknown")
        font_size = char.get("size", 12)
        font_key = f"{font_name}_{font_size}"
        
        # Initialize metrics for this font variant if not exists
        if font_key not in font_metrics:
            font_metrics[font_key] = {
                "font_name": font_name,
                "font_size": font_size,
                "standard_char_width": None,  # Width of a representative character for this font
                "char_samples": [],  # Store multiple samples for better selection
                "sample_count": 0
            }
        
        metrics = font_metrics[font_key]
        
        # Calculate actual character width from bounding box
        char_text = char.get("text", "")
        if char_text and char_text.strip():  # Skip whitespace and empty chars
            actual_width = char.get("x1", 0) - char.get("x0", 0)
            
            # Collect samples from first few characters to find a representative width
            if metrics["standard_char_width"] is None and len(metrics["char_samples"]) < 10:
                # Only collect reasonable width samples (avoid extreme outliers)
                expected_range = (font_size * 0.2, font_size * 1.2)  # 20% to 120% of font size
                if expected_range[0] <= actual_width <= expected_range[1]:
                    metrics["char_samples"].append({
                        'width': actual_width, 
                        'char': char_text,
                        'sample_index': metrics["sample_count"]
                    })
                    
                    # Once we have 5 reasonable samples, pick the median
                    if len(metrics["char_samples"]) >= 5:
                        widths = [s['width'] for s in metrics["char_samples"]]
                        widths.sort()
                        median_width = widths[len(widths)//2]  # Pick median for stability
                        median_sample = next(s for s in metrics["char_samples"] if s['width'] == median_width)
                        metrics["standard_char_width"] = median_width
                        logger.debug(f"Captured standard char width for {font_key}: {median_width:.3f}pt from char '{median_sample['char']}' (median of {len(widths)} samples)")
                        # Clean up samples to save memory
                        metrics["char_samples"] = []
            
            metrics["sample_count"] += 1
    
    # Log font metrics summary
    for font_key, metrics in font_metrics.items():
        if metrics["sample_count"] > 0 and metrics["standard_char_width"] is not None:
            logger.debug(f"Font {font_key}: standard_char_width={metrics['standard_char_width']:.3f}pt, {metrics['sample_count']} total chars")
    
    return font_metrics


# Function to extract text metadata from a PDF file
def extract_text_metadata(pdf_path, max_pages=None):
    """
    Extract text metadata from a PDF file, including character width measurements.

    Args:
        pdf_path: Path to the PDF file.
        max_pages: Maximum number of pages to process (None for all pages).

    Returns:
        Dictionary containing text metadata for all processed pages.
    """
    all_pages_data = {"paragraphs": [], "lines": [], "words": [], "chars": [], "font_metrics": {}}

    try:
        with pdfplumber.open(pdf_path) as pdf:
            # Limit pages if max_pages is specified
            pages_to_process = pdf.pages[:max_pages] if max_pages else pdf.pages

            for page_number, page in enumerate(pages_to_process, start=1):
                try:
                    # Extract character-level data
                    char_data = page.chars

                    # Extract font metrics from character data
                    font_metrics = extract_font_metrics(char_data)
                    
                    # Merge font metrics into global metrics
                    for font_key, metrics in font_metrics.items():
                        if font_key not in all_pages_data["font_metrics"]:
                            all_pages_data["font_metrics"][font_key] = metrics
                        else:
                            # Update with more character samples 
                            existing = all_pages_data["font_metrics"][font_key]
                            
                            # Merge character width samples for better accuracy
                            if existing["standard_char_width"] is None and metrics["standard_char_width"] is not None:
                                existing["standard_char_width"] = metrics["standard_char_width"]
                            elif existing["standard_char_width"] is None:
                                # Merge samples if both still collecting
                                if "char_samples" in existing and "char_samples" in metrics:
                                    existing["char_samples"].extend(metrics["char_samples"])
                            
                            existing["sample_count"] += metrics["sample_count"]

                    # Extract words
                    words = page.extract_words()

                    # Detect lines and paragraphs
                    lines, paragraphs = detect_lines_and_paragraphs(char_data)

                    # Add page number and font metrics to each paragraph
                    for paragraph in paragraphs:
                        paragraph["page_number"] = page_number
                        # Add font metrics reference for precise width calculation
                        font_key = f"{paragraph.get('font_name', 'Unknown')}_{paragraph.get('font_size', 12)}"
                        if font_key in all_pages_data["font_metrics"]:
                            paragraph["font_metrics"] = all_pages_data["font_metrics"][font_key]

                    # Add data to the aggregated result
                    all_pages_data["paragraphs"].extend(paragraphs)
                    all_pages_data["lines"].extend(lines)
                    all_pages_data["words"].extend(words)
                    all_pages_data["chars"].extend(char_data)

                    logger.debug(
                        f"Processed page {page_number} with {len(paragraphs)} paragraphs and {len(font_metrics)} font variants"
                    )

                except Exception as e:
                    logger.error(f"Error processing page {page_number}: {e}")

            logger.info(
                f"Extracted {len(all_pages_data['paragraphs'])} paragraphs from {len(pages_to_process)} pages"
            )
            logger.info(
                f"Collected font metrics for {len(all_pages_data['font_metrics'])} font variants"
            )
            return all_pages_data

    except Exception as e:
        logger.error(f"Error opening PDF file {pdf_path}: {e}")
        return all_pages_data


def detect_columns_by_gaps(chars, page_width):
    """
    Detect column boundaries by analyzing horizontal gaps between characters.
    Returns column boundaries that can handle mixed single/multi-column layouts.
    """
    if not chars:
        return [0, page_width]

    # Sort characters by horizontal position
    sorted_chars = sorted(chars, key=lambda c: c["x0"])

    # Find significant horizontal gaps
    gaps = []
    for i in range(1, len(sorted_chars)):
        prev_char = sorted_chars[i - 1]
        curr_char = sorted_chars[i]
        gap_size = curr_char["x0"] - prev_char["x1"]

        # Consider gaps that are larger than typical word spacing
        avg_char_width = prev_char.get("size", 12) * 0.6  # Approximate character width
        min_gap_threshold = avg_char_width * 1.5  # Even more reduced threshold

        if gap_size > min_gap_threshold:
            gaps.append(
                {
                    "position": (prev_char["x1"] + curr_char["x0"]) / 2,
                    "size": gap_size,
                    "y_range": (
                        min(prev_char["y0"], curr_char["y0"]),
                        max(prev_char["y1"], curr_char["y1"]),
                    ),
                    "prev_x1": prev_char["x1"],
                    "curr_x0": curr_char["x0"],
                }
            )

    if not gaps:
        logger.debug("No significant gaps found - treating as single column")
        return [0, page_width]

    # Group gaps by position (merge nearby gaps)
    gap_groups = []
    sorted_gaps = sorted(gaps, key=lambda g: g["position"])

    current_group = [sorted_gaps[0]]
    for gap in sorted_gaps[1:]:
        if (
            abs(gap["position"] - current_group[-1]["position"]) < 30
        ):  # Within 30 points
            current_group.append(gap)
        else:
            gap_groups.append(current_group)
            current_group = [gap]
    gap_groups.append(current_group)

    # Analyze each gap group for column separation potential
    column_gaps = []
    page_height = max(c["y1"] for c in chars) - min(c["y0"] for c in chars)

    for gap_group in gap_groups:
        # Calculate average properties of gap group
        avg_position = sum(g["position"] for g in gap_group) / len(gap_group)
        avg_size = sum(g["size"] for g in gap_group) / len(gap_group)
        total_y_coverage = max(g["y_range"][1] for g in gap_group) - min(
            g["y_range"][0] for g in gap_group
        )

        # Consider as column separator if:
        # 1. Gap is large enough (> 10 points or > 5% of page width)
        # 2. Spans significant vertical area (> 10% of content height)
        if (
            avg_size > 10 or avg_size > page_width * 0.05
        ) and total_y_coverage > page_height * 0.1:
            column_gaps.append(
                {
                    "position": avg_position,
                    "size": avg_size,
                    "coverage": total_y_coverage,
                }
            )

    # Create column boundaries
    boundaries = [0]
    for gap in sorted(column_gaps, key=lambda g: g["position"]):
        boundaries.append(gap["position"])
    boundaries.append(page_width)

    logger.debug(
        f"Found {len(gaps)} total gaps, {len(gap_groups)} gap groups, {len(column_gaps)} column separators"
    )
    logger.debug(f"Page dimensions: width={page_width:.1f}, height={page_height:.1f}")
    if len(gaps) > 0:
        max_gap = max(gaps, key=lambda g: g["size"])
        logger.debug(
            f"Largest gap: size={max_gap['size']:.1f}, pos={max_gap['position']:.1f}"
        )
    logger.debug(
        f"Detected {len(boundaries)-1} columns with boundaries: {[f'{b:.1f}' for b in boundaries]}"
    )
    if column_gaps:
        for i, gap in enumerate(column_gaps):
            logger.debug(
                f"Column gap {i+1}: pos={gap['position']:.1f}, size={gap['size']:.1f}, coverage={gap['coverage']:.1f}"
            )

    return boundaries


def group_chars_by_columns(chars, column_boundaries):
    """
    Group characters into columns based on boundaries.
    """
    columns = [[] for _ in range(len(column_boundaries) - 1)]

    for char in chars:
        char_center_x = (char["x0"] + char["x1"]) / 2

        # Find which column this character belongs to
        for i in range(len(column_boundaries) - 1):
            if column_boundaries[i] <= char_center_x < column_boundaries[i + 1]:
                columns[i].append(char)
                break
        else:
            # If not within any boundary, assign to closest column
            closest_col = min(
                range(len(columns)),
                key=lambda i: min(
                    abs(char_center_x - column_boundaries[i]),
                    abs(char_center_x - column_boundaries[i + 1]),
                ),
            )
            columns[closest_col].append(char)

    return columns


def detect_lines_and_paragraphs(chars):
    """
    Group characters into lines and paragraphs using line-first column detection.
    This approach groups by Y-position first, then analyzes gaps within lines.
    """
    if not chars:
        return [], []

    logger.debug(f"Processing {len(chars)} characters for line and paragraph detection")

    # Step 1: Group characters by vertical position (lines)
    lines_by_y = {}
    for char in chars:
        y_pos = round(char["y0"], 1)  # Round to nearest 0.1 point for grouping
        if y_pos not in lines_by_y:
            lines_by_y[y_pos] = []
        lines_by_y[y_pos].append(char)

    logger.debug(f"Found {len(lines_by_y)} distinct Y-positions (lines)")

    # Step 2: Analyze each line for column patterns
    column_segments = []
    sorted_y_positions = sorted(lines_by_y.keys(), reverse=True)  # Top to bottom

    for y_pos in sorted_y_positions:
        line_chars = sorted(lines_by_y[y_pos], key=lambda c: c["x0"])  # Left to right

        # Find gaps within this line
        line_segments = []
        current_segment = []

        for i, char in enumerate(line_chars):
            if not current_segment:
                current_segment.append(char)
            else:
                # Check gap between current char and previous char
                prev_char = current_segment[-1]
                gap_size = char["x0"] - prev_char["x1"]

                # Use dynamic threshold based on font size
                threshold = max(
                    20, char.get("size", 12) * 2
                )  # At least 20 points or 2x font size

                if gap_size > threshold:
                    # Large gap found - end current segment and start new one
                    line_segments.append(current_segment)
                    current_segment = [char]
                else:
                    current_segment.append(char)

        if current_segment:
            line_segments.append(current_segment)

        # Store segments with their Y position
        for seg_idx, segment in enumerate(line_segments):
            column_segments.append(
                {
                    "y_pos": y_pos,
                    "column": seg_idx,
                    "chars": segment,
                    "x_start": min(c["x0"] for c in segment),
                    "x_end": max(c["x1"] for c in segment),
                    "text": "".join(c["text"] for c in segment),
                }
            )

    logger.debug(f"Created {len(column_segments)} column segments")

    # Step 3: Group segments by column based on horizontal alignment
    column_groups = {}

    for segment in column_segments:
        # Find which column this segment belongs to based on x_start position
        col_key = None

        # Look for existing column with similar x_start (within 50 points)
        for existing_col in column_groups.keys():
            if abs(segment["x_start"] - existing_col) < 50:
                col_key = existing_col
                break

        # If no existing column found, create new one
        if col_key is None:
            col_key = segment["x_start"]
            column_groups[col_key] = []

        column_groups[col_key].append(segment)

    # Sort columns by x-position (left to right)
    sorted_columns = sorted(column_groups.items(), key=lambda x: x[0])
    logger.debug(
        f"Detected {len(sorted_columns)} columns at x-positions: {[f'{x:.1f}' for x, _ in sorted_columns]}"
    )

    # Step 4: Group segments into paragraphs within each column
    all_paragraphs = []

    for col_idx, (col_x, segments) in enumerate(sorted_columns):
        # Sort segments by Y position (top to bottom)
        segments.sort(key=lambda s: -s["y_pos"])

        logger.debug(f"Processing column {col_idx + 1} with {len(segments)} segments")

        # Group consecutive segments into paragraphs
        paragraphs = []
        current_paragraph = []

        for segment in segments:
            if not current_paragraph:
                current_paragraph.append(segment)
            else:
                # Check vertical gap between segments
                prev_y = current_paragraph[-1]["y_pos"]
                curr_y = segment["y_pos"]
                y_gap = abs(prev_y - curr_y)

                # Use font size to determine paragraph breaks
                font_size = (
                    segment["chars"][0].get("size", 12) if segment["chars"] else 12
                )
                paragraph_threshold = font_size * 1.5  # 1.5x font size

                if y_gap > paragraph_threshold:
                    paragraphs.append(current_paragraph)
                    current_paragraph = [segment]
                else:
                    current_paragraph.append(segment)

        if current_paragraph:
            paragraphs.append(current_paragraph)

            # Convert paragraphs to output format
        for paragraph in paragraphs:
            # Combine text from all segments in paragraph
            paragraph_text = " ".join(seg["text"] for seg in paragraph)

            # Skip empty paragraphs
            if not paragraph_text.strip():
                continue

            # Get styling info from first character
            first_char = (
                paragraph[0]["chars"][0] if paragraph and paragraph[0]["chars"] else {}
            )

            # Calculate bounding box
            all_chars = [char for seg in paragraph for char in seg["chars"]]
            x0 = min(c["x0"] for c in all_chars)
            y0 = min(c["y0"] for c in all_chars)
            x1 = max(c["x1"] for c in all_chars)
            y1 = max(c["y1"] for c in all_chars)

            # Count the number of lines in this paragraph
            num_lines = len(paragraph)

            # Count number of distinct y-positions (more accurate line count)
            y_positions = set(round(seg["y_pos"], 1) for seg in paragraph)
            distinct_lines = len(y_positions)

            formatted_paragraph = {
                "text": paragraph_text,
                "font_name": first_char.get("fontname", ""),
                "font_size": first_char.get("size", 0),
                "non_stroking_color": first_char.get("non_stroking_color", ""),
                "stroking_color": first_char.get("stroking_color", ""),
                "bounding_box": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "column": col_idx,
                "num_lines": distinct_lines,  # Add line count metadata
                "segments": num_lines,  # Original segment count (may differ from distinct lines)
            }

            all_paragraphs.append(formatted_paragraph)

    # Step 5: Sort paragraphs by reading order (top-to-bottom, left-to-right)
    all_paragraphs.sort(
        key=lambda p: (-p["bounding_box"]["y1"], p["bounding_box"]["x0"])
    )

    logger.debug(f"Generated {len(all_paragraphs)} paragraphs")

    return [], all_paragraphs  # Return empty lines since we're focusing on paragraphs


def calculate_reading_order_score(cluster, page_height):
    """
    Calculate reading order score for proper sorting
    Formula: (page_height - y_center) * 1000 + x_center

    Args:
        cluster: Text cluster with center_x, center_y properties
        page_height: Total page height for Y-coordinate normalization

    Returns:
        float: Reading order score (higher = earlier in reading order)
    """
    y_component = (page_height - cluster["center_y"]) * 1000
    x_component = cluster["center_x"]
    return y_component + x_component


def sort_groups_by_reading_order(groups, page_height):
    """
    Sort text groups by natural reading order (top-to-bottom, left-to-right)

    This ensures correct translation sequence regardless of initial grouping
    """
    for group in groups:
        group["reading_order_score"] = calculate_reading_order_score(group, page_height)

    sorted_groups = sorted(groups, key=lambda g: g["reading_order_score"], reverse=True)
    return sorted_groups


def detect_columns(chars, page_width):
    """
    Detect columns based on horizontal gaps between clusters of text.

    Args:
        chars: List of character dictionaries with bounding box info.
        page_width: Total width of the page.

    Returns:
        List of column boundaries (x-coordinates).
    """
    # Sort characters by their horizontal position (x0)
    chars = sorted(chars, key=lambda c: c["x0"])

    # Identify large horizontal gaps to determine column boundaries
    column_boundaries = []
    last_x1 = 0
    for char in chars:
        if (
            char["x0"] - last_x1 > page_width * 0.03
        ):  # Adjusted gap threshold (3% of page width)
            column_boundaries.append(last_x1)
        last_x1 = char["x1"]
    column_boundaries.append(last_x1)

    logger.debug(f"Detected column boundaries: {column_boundaries}")
    return column_boundaries


def assign_to_columns(chars, column_boundaries):
    """
    Assign characters to columns based on their horizontal position.

    Args:
        chars: List of character dictionaries with bounding box info.
        column_boundaries: List of column boundaries (x-coordinates).

    Returns:
        List of columns, each containing a list of characters.
    """
    columns = [[] for _ in range(len(column_boundaries) - 1)]

    for char in chars:
        assigned = False
        for i in range(len(column_boundaries) - 1):
            if column_boundaries[i] <= char["x0"] < column_boundaries[i + 1]:
                columns[i].append(char)
                assigned = True
                break
        if not assigned:
            # Assign to the closest column if not within boundaries
            closest_index = min(
                range(len(column_boundaries) - 1),
                key=lambda i: abs(
                    (column_boundaries[i] + column_boundaries[i + 1]) / 2 - char["x0"]
                ),
            )
            columns[closest_index].append(char)

    for i, column in enumerate(columns):
        logger.debug(f"Column {i + 1}: {len(column)} characters")

    return columns


def group_characters_for_translation(chars, page_width, page_height):
    """
    Main grouping function prioritizing reading order correctness and handling multi-column layouts.
    """
    # Step 1: Detect columns
    column_boundaries = detect_columns(chars, page_width)

    # Step 2: Assign characters to columns
    columns = assign_to_columns(chars, column_boundaries)

    # Step 3: Group characters within each column
    final_groups = []
    for column in columns:
        clusters = []
        current_cluster = []

        # Sort characters by vertical position (y0) and then horizontal position (x0)
        column = sorted(column, key=lambda c: (-c["y0"], c["x0"]))

        for char in column:
            if not current_cluster:
                current_cluster.append(char)
            else:
                last_char = current_cluster[-1]
                y_diff = abs(char["y0"] - last_char["y0"])
                x_gap = abs(char["x0"] - last_char["x1"])
                font_size_diff = abs(char["size"] - last_char["size"])

                if (
                    y_diff > char["size"] * 0.8
                    or x_gap > char["size"] * 6
                    or font_size_diff > 2
                ):
                    clusters.append(current_cluster)
                    current_cluster = [char]
                else:
                    current_cluster.append(char)

        if current_cluster:
            clusters.append(current_cluster)

        # Convert clusters to final group format
        for cluster in clusters:
            x0 = min(c["x0"] for c in cluster)
            y0 = min(c["y0"] for c in cluster)
            x1 = max(c["x1"] for c in cluster)
            y1 = max(c["y1"] for c in cluster)

            group = {
                "text": "".join(c["text"] for c in cluster),
                "bbox": {"x0": x0, "y0": y0, "x1": x1, "y1": y1},
                "characters": cluster,
                "center_x": (x0 + x1) / 2,
                "center_y": (y0 + y1) / 2,
            }
            group["reading_order_score"] = calculate_reading_order_score(
                group, page_height
            )
            final_groups.append(group)

    # Step 4: Sort all groups by reading order
    final_groups = sort_groups_by_reading_order(final_groups, page_height)

    return final_groups
