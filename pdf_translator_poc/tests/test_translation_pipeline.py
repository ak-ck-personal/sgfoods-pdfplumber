#!/usr/bin/env python
# test_translation_pipeline.py
# Test script to verify the complete PDF translation pipeline

import os
import sys
import json
import logging
import argparse
from datetime import datetime
import pdfplumber

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

# Import all the pipeline modules
from src.extractor import extract_text_metadata
from src.translator import translate_paragraphs
from src.text_fitter import process_paragraphs
from src.overlay_generator import generate_overlay
from src.merger import merge_pdfs
from config.settings import DEFAULT_TARGET_LANGUAGE

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def translate_pdf_complete(
    input_pdf_path,
    output_pdf_path,
    target_language=DEFAULT_TARGET_LANGUAGE,
    font_dir=None,
    temp_dir=None,
    max_pages=None,
    debug=False
):
    """
    Complete PDF translation pipeline using overlay approach
    
    Args:
        input_pdf_path: Path to input PDF file
        output_pdf_path: Path to save translated PDF
        target_language: Target language code (e.g., 'vi', 'en', 'ja')
        font_dir: Directory containing font files
        temp_dir: Directory for temporary files
        max_pages: Maximum number of pages to process (None for all)
        debug: Enable debug mode (saves intermediate files)
    
    Returns:
        Path to translated PDF if successful, None if failed
    """
    try:
        logger.info(f"Starting PDF translation pipeline")
        logger.info(f"Input: {input_pdf_path}")
        logger.info(f"Output: {output_pdf_path}")
        logger.info(f"Target language: {target_language}")
        logger.info(f"Max pages: {max_pages or 'all'}")
        
        # Create temp directory if not provided
        if not temp_dir:
            temp_dir = os.path.join(os.path.dirname(output_pdf_path), "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        # Generate timestamped filenames for intermediate files
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
        
        extracted_json = os.path.join(temp_dir, f"{base_name}_extracted_{timestamp}.json")
        translated_json = os.path.join(temp_dir, f"{base_name}_translated_{timestamp}.json")
        fitted_json = os.path.join(temp_dir, f"{base_name}_fitted_{timestamp}.json")
        overlay_pdf = os.path.join(temp_dir, f"{base_name}_overlay_{timestamp}.pdf")
        
        # Step 1: Extract text metadata from PDF
        logger.info("Step 1: Extracting text metadata from PDF...")
        extracted_data = extract_text_metadata(input_pdf_path, max_pages=max_pages)
        
        if not extracted_data or not extracted_data.get("paragraphs"):
            logger.error("No paragraphs extracted from PDF")
            return None
            
        logger.info(f"Extracted {len(extracted_data['paragraphs'])} paragraphs")
        
        # Save extracted data if debug mode
        if debug:
            with open(extracted_json, 'w', encoding='utf-8') as f:
                json.dump(extracted_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved extracted data to: {extracted_json}")
        
        # Step 2: Translate paragraphs
        logger.info("Step 2: Translating paragraphs...")
        translated_paragraphs = translate_paragraphs(extracted_data["paragraphs"], target_language)
        
        if not translated_paragraphs:
            logger.error("Translation failed")
            return None
            
        logger.info(f"Translated {len(translated_paragraphs)} paragraphs")
        
        # Save translated data if debug mode
        if debug:
            with open(translated_json, 'w', encoding='utf-8') as f:
                json.dump(translated_paragraphs, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved translated data to: {translated_json}")
        
        # Step 3: Fit translated text to original paragraph bounds
        logger.info("Step 3: Fitting translated text to paragraph bounds...")
        fitted_paragraphs = process_paragraphs(translated_paragraphs)
        
        if not fitted_paragraphs:
            logger.error("Text fitting failed")
            return None
            
        logger.info(f"Fitted {len(fitted_paragraphs)} paragraphs")
        
        # Save fitted data if debug mode
        if debug:
            with open(fitted_json, 'w', encoding='utf-8') as f:
                json.dump(fitted_paragraphs, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved fitted data to: {fitted_json}")
        
        # Step 4: Generate overlay PDF with white masks and translated text
        logger.info("Step 4: Generating overlay PDF...")
        
        # Get page size from the original PDF
        with pdfplumber.open(input_pdf_path) as pdf:
            if pdf.pages:
                first_page = pdf.pages[0]
                page_size = (first_page.width, first_page.height)
            else:
                page_size = (612, 792)  # Default letter size
        
        overlay_path = generate_overlay(
            fitted_paragraphs,
            overlay_pdf,
            page_size=page_size,
            font_dir=font_dir,
            target_language=target_language,
            debug_outline=True  # Enable red outline debugging
        )
        
        if not overlay_path or not os.path.exists(overlay_path):
            logger.error("Overlay generation failed")
            return None
            
        logger.info(f"Generated overlay PDF: {overlay_path}")
        
        # Step 5: Merge overlay with original PDF
        logger.info("Step 5: Merging overlay with original PDF...")
        final_pdf = merge_pdfs(
            input_pdf_path,
            overlay_path,
            output_pdf_path
        )
        
        if not final_pdf or not os.path.exists(final_pdf):
            logger.error("PDF merging failed")
            return None
            
        logger.info(f"Translation completed successfully: {final_pdf}")
        
        # Clean up temporary files if not in debug mode
        if not debug:
            try:
                if os.path.exists(overlay_path):
                    os.remove(overlay_path)
                logger.debug("Cleaned up temporary overlay file")
            except Exception as e:
                logger.warning(f"Could not clean up temporary files: {e}")
        
        return final_pdf
        
    except Exception as e:
        logger.error(f"Translation pipeline failed: {e}")
        logger.exception("Full error details:")
        return None


def main():
    """Run test of the complete PDF translation pipeline"""
    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Test the PDF translation pipeline")
    parser.add_argument("pdf_path", help="Path to the PDF file to translate")
    parser.add_argument(
        "-t",
        "--target",
        default=DEFAULT_TARGET_LANGUAGE,
        help=f"Target language code (default: {DEFAULT_TARGET_LANGUAGE})",
    )
    parser.add_argument("-f", "--font-dir", help="Directory containing font files")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (creates additional output files)",
    )
    args = parser.parse_args()

    # Set debug logging if requested
    if args.debug:
        logger.setLevel(logging.DEBUG)
        for handler in logger.handlers:
            handler.setLevel(logging.DEBUG)

    # Validate PDF path
    if not os.path.exists(args.pdf_path):
        logger.error(f"PDF file not found: {args.pdf_path}")
        return 1

    # Create output directory in same location as input PDF
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_basename = os.path.splitext(os.path.basename(args.pdf_path))[0]
    output_dir = os.path.join(
        os.path.dirname(args.pdf_path), f"test_translation_{timestamp}"
    )
    os.makedirs(output_dir, exist_ok=True)

    # Define output PDF path
    output_pdf = os.path.join(output_dir, f"translated_{pdf_basename}.pdf")

    # Define temp directory
    temp_dir = os.path.join(output_dir, "temp")
    os.makedirs(temp_dir, exist_ok=True)

    logger.info(f"Starting translation test of: {args.pdf_path}")
    logger.info(f"Target language: {args.target}")
    logger.info(f"Output will be saved to: {output_pdf}")

    # Run the translation pipeline
    try:
        # Limit processing to only 2 pages
        result = translate_pdf_complete(
            input_pdf_path=args.pdf_path,
            output_pdf_path=output_pdf,
            target_language=args.target,
            font_dir=args.font_dir,
            temp_dir=temp_dir,
            max_pages=2,  # Process only 2 pages
            debug=args.debug,
        )

        if result:
            logger.info("✅ Test completed successfully!")
            logger.info(f"Translated PDF: {output_pdf}")
            return 0
        else:
            logger.error("❌ Test failed: Translation pipeline returned None")
            return 1

    except Exception as e:
        logger.exception(f"❌ Test failed with error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
