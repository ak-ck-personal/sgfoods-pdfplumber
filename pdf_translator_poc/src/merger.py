# merger.py
# Module for final PDF assembly

import os
import logging
import tempfile
import shutil
from PyPDF2 import PdfReader, PdfWriter, errors

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def _copy_temp_to_output(temp_path, output_pdf_path):
    """
    Helper function to safely copy a temporary PDF file to the final output location.
    Works across different drives by using copy instead of rename.

    Args:
        temp_path: Path to the temporary PDF file
        output_pdf_path: Path where the final PDF should be saved
    """
    # Remove the target file if it already exists
    if os.path.exists(output_pdf_path):
        os.remove(output_pdf_path)

    # Copy the file (works across different drives)
    shutil.copy2(temp_path, output_pdf_path)

    # Remove the temporary file after copying
    os.remove(temp_path)

    return output_pdf_path


# Function to merge original and overlay PDFs
def merge_pdfs(original_pdf_path, overlay_pdf_path, output_pdf_path):
    """
    Merge an original PDF with an overlay PDF containing translations

    Args:
        original_pdf_path: Path to the original PDF file
        overlay_pdf_path: Path to the overlay PDF with white masks and translations
        output_pdf_path: Path where the merged PDF will be saved

    Returns:
        Path to the merged PDF file
    """
    try:
        logger.info(
            f"Merging original PDF ({original_pdf_path}) with overlay ({overlay_pdf_path})"
        )

        # Check if input files exist
        if not os.path.exists(original_pdf_path):
            raise FileNotFoundError(f"Original PDF not found: {original_pdf_path}")
        if not os.path.exists(overlay_pdf_path):
            raise FileNotFoundError(f"Overlay PDF not found: {overlay_pdf_path}")

        # Open the PDF files
        original_reader = PdfReader(original_pdf_path)
        overlay_reader = PdfReader(overlay_pdf_path)
        writer = PdfWriter()

        # Check page count mismatch
        if len(original_reader.pages) != len(overlay_reader.pages):
            logger.warning(
                f"Page count mismatch: Original has {len(original_reader.pages)} pages, "
                f"overlay has {len(overlay_reader.pages)} pages"
            )

        # Merge pages
        for i, page in enumerate(original_reader.pages):
            if i < len(overlay_reader.pages):
                logger.debug(f"Merging page {i+1}")
                page.merge_page(overlay_reader.pages[i])
            else:
                logger.warning(f"No overlay for page {i+1}, keeping original")
            writer.add_page(page)

        # Use a temporary file to avoid issues with file locks
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_path = temp_file.name

        # Write to the temporary file first
        with open(temp_path, "wb") as output_file:
            writer.write(output_file)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Copy the temporary file to the final location
        _copy_temp_to_output(temp_path, output_pdf_path)

        logger.info(f"Successfully created merged PDF: {output_pdf_path}")
        return output_pdf_path

    except errors.PdfReadError as e:
        logger.error(f"PDF read error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error merging PDFs: {str(e)}")
        # Clean up temporary file if it exists
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise


def merge_pdfs_in_batches(
    original_pdf_path, overlay_pdf_path, output_pdf_path, batch_size=10
):
    """
    Merge large PDFs in batches to reduce memory usage

    Args:
        original_pdf_path: Path to the original PDF file
        overlay_pdf_path: Path to the overlay PDF with white masks and translations
        output_pdf_path: Path where the merged PDF will be saved
        batch_size: Number of pages to process in each batch

    Returns:
        Path to the merged PDF file
    """
    try:
        logger.info(f"Merging PDFs in batches of {batch_size} pages")

        # Check if input files exist
        if not os.path.exists(original_pdf_path):
            raise FileNotFoundError(f"Original PDF not found: {original_pdf_path}")
        if not os.path.exists(overlay_pdf_path):
            raise FileNotFoundError(f"Overlay PDF not found: {overlay_pdf_path}")

        # Open the PDF files
        original_reader = PdfReader(original_pdf_path)
        overlay_reader = PdfReader(overlay_pdf_path)
        writer = PdfWriter()

        # Process pages in batches
        total_pages = len(original_reader.pages)
        for i in range(0, total_pages, batch_size):
            end = min(i + batch_size, total_pages)
            logger.info(f"Processing pages {i+1} to {end} (of {total_pages})")

            # Process each page in the current batch
            for j in range(i, end):
                if j < len(overlay_reader.pages):
                    # Create a new page by merging original and overlay
                    page = original_reader.pages[j]
                    page.merge_page(overlay_reader.pages[j])
                    writer.add_page(page)
                else:
                    # Add original page without overlay
                    writer.add_page(original_reader.pages[j])

        # Use a temporary file to avoid issues with file locks
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_path = temp_file.name

        # Write to the temporary file first
        with open(temp_path, "wb") as output_file:
            writer.write(output_file)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Copy the temporary file to the final location
        _copy_temp_to_output(temp_path, output_pdf_path)

        logger.info(f"Successfully created merged PDF: {output_pdf_path}")
        return output_pdf_path

    except Exception as e:
        logger.error(f"Error merging PDFs in batches: {str(e)}")
        # Clean up temporary file if it exists
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise


def merge_selected_pages(
    original_pdf_path, overlay_pdf_path, output_pdf_path, page_indices=None
):
    """
    Merge only selected pages from original and overlay PDFs

    Args:
        original_pdf_path: Path to the original PDF file
        overlay_pdf_path: Path to the overlay PDF with white masks and translations
        output_pdf_path: Path where the merged PDF will be saved
        page_indices: List of 0-based page indices to include (None for all pages)

    Returns:
        Path to the merged PDF file with selected pages
    """
    try:
        logger.info(f"Merging selected pages from PDFs")

        # Check if input files exist
        if not os.path.exists(original_pdf_path):
            raise FileNotFoundError(f"Original PDF not found: {original_pdf_path}")
        if not os.path.exists(overlay_pdf_path):
            raise FileNotFoundError(f"Overlay PDF not found: {overlay_pdf_path}")

        # Open the PDF files
        original_reader = PdfReader(original_pdf_path)
        overlay_reader = PdfReader(overlay_pdf_path)
        writer = PdfWriter()

        # Use all pages if no specific indices are provided
        if page_indices is None:
            page_indices = range(len(original_reader.pages))

        # Add selected pages
        for i in page_indices:
            if i < len(original_reader.pages):
                page = original_reader.pages[i]

                # Merge with overlay if available
                if i < len(overlay_reader.pages):
                    page.merge_page(overlay_reader.pages[i])

                writer.add_page(page)
            else:
                logger.warning(f"Page index {i} is out of range")

        # Use a temporary file to avoid issues with file locks
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_path = temp_file.name

        # Write to the temporary file first
        with open(temp_path, "wb") as output_file:
            writer.write(output_file)

        # Create output directory if it doesn't exist
        output_dir = os.path.dirname(output_pdf_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Copy the temporary file to the final location
        _copy_temp_to_output(temp_path, output_pdf_path)

        logger.info(
            f"Successfully created merged PDF with {len(page_indices)} pages: {output_pdf_path}"
        )
        return output_pdf_path

    except Exception as e:
        logger.error(f"Error merging selected PDF pages: {str(e)}")
        # Clean up temporary file if it exists
        if "temp_path" in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass
        raise


def verify_pdf_integrity(pdf_path):
    """
    Verify that a PDF file is valid and can be opened

    Args:
        pdf_path: Path to the PDF file to verify

    Returns:
        Boolean indicating if the PDF is valid
    """
    try:
        # Try to open and read basic info
        reader = PdfReader(pdf_path)
        page_count = len(reader.pages)
        metadata = reader.metadata

        logger.info(f"PDF verified: {pdf_path} ({page_count} pages)")
        return True

    except Exception as e:
        logger.error(f"PDF verification failed: {pdf_path} - {str(e)}")
        return False


def get_pdf_info(pdf_path):
    """
    Get basic information about a PDF file

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with PDF information or None if invalid
    """
    try:
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF file not found: {pdf_path}")

        reader = PdfReader(pdf_path)

        info = {
            "path": pdf_path,
            "filename": os.path.basename(pdf_path),
            "page_count": len(reader.pages),
            "file_size_bytes": os.path.getsize(pdf_path),
            "file_size_mb": os.path.getsize(pdf_path) / (1024 * 1024),
        }

        # Try to get metadata (might not be available in all PDFs)
        try:
            metadata = reader.metadata
            if metadata:
                info["title"] = metadata.get("/Title", "")
                info["author"] = metadata.get("/Author", "")
                info["subject"] = metadata.get("/Subject", "")
                info["creator"] = metadata.get("/Creator", "")
                info["producer"] = metadata.get("/Producer", "")
                info["creation_date"] = metadata.get("/CreationDate", "")
                info["modification_date"] = metadata.get("/ModDate", "")
        except:
            # Continue without metadata
            pass

        return info

    except Exception as e:
        logger.error(f"Error getting PDF info: {str(e)}")
        return None


# Main function for standalone execution
if __name__ == "__main__":
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description="Merge original PDF with overlay translation"
    )
    parser.add_argument("original", help="Path to original PDF file")
    parser.add_argument("overlay", help="Path to overlay PDF file with translations")
    parser.add_argument("output", help="Path to save the merged PDF file")
    parser.add_argument(
        "--batch",
        type=int,
        default=0,
        help="Batch size for processing large PDFs (0 for single batch)",
    )
    parser.add_argument(
        "--pages",
        type=str,
        help="Comma-separated list of page numbers to include (1-based)",
    )

    args = parser.parse_args()

    try:
        # Process page selection if specified
        page_indices = None
        if args.pages:
            # Convert 1-based page numbers to 0-based indices
            page_indices = [int(p) - 1 for p in args.pages.split(",")]
            merge_selected_pages(args.original, args.overlay, args.output, page_indices)

        # Use batch processing for large PDFs
        elif args.batch > 0:
            merge_pdfs_in_batches(args.original, args.overlay, args.output, args.batch)

        # Use standard processing
        else:
            merge_pdfs(args.original, args.overlay, args.output)

        # Verify the output PDF
        if verify_pdf_integrity(args.output):
            # Get and display info about the result
            info = get_pdf_info(args.output)
            if info:
                print(f"\nMerged PDF information:")
                print(f"File: {info['filename']}")
                print(f"Pages: {info['page_count']}")
                print(f"Size: {info['file_size_mb']:.2f} MB")
                if "title" in info and info["title"]:
                    print(f"Title: {info['title']}")

            print(f"\nSuccessfully created merged PDF: {args.output}")
        else:
            print(
                f"\nWarning: The output PDF might have issues. Please check: {args.output}"
            )

    except Exception as e:
        print(f"Error: {str(e)}")
        exit(1)
