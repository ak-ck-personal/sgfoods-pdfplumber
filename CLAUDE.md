# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SGFoods is a Python PDF translation tool that uses AWS Translate with an overlay approach to preserve original document formatting, tables, images, and layout while replacing only text content with translations.

## Development Environment

- **Python Environment**: Uses a virtual environment located at `pdf_translator_env/`
- **Package Management**: No requirements.txt or setup.py found - dependencies are installed directly in virtual environment
- **Key Dependencies**: pdfplumber, boto3, PyPDF2, reportlab, pillow, pdfminer-six

### Virtual Environment Activation
```bash
# On Windows/WSL
source pdf_translator_env/Scripts/activate
# or
pdf_translator_env/Scripts/python.exe <script>
```

## Common Commands

### Running Tests
```bash
# Run the main translation pipeline test (processes first 2 pages only)
python pdf_translator_poc/tests/test_translation_pipeline.py <pdf_path> [-t target_language] [--debug]

# Examples:
python pdf_translator_poc/tests/test_translation_pipeline.py documents/circular.pdf -t en
python pdf_translator_poc/tests/test_translation_pipeline.py documents/circular.pdf -t ja --debug
```

### Development Scripts
- Main test script: `pdf_translator_poc/tests/test_translation_pipeline.py` - Tests complete translation pipeline

## Architecture

The project uses a modular 5-stage PDF translation pipeline:

### Core Modules (`pdf_translator_poc/src/`)

1. **extractor.py**: PDF text extraction using pdfplumber
   - Extracts character-level data with coordinates (x0, y0, x1, y1)
   - Groups characters into lines and paragraphs based on spatial proximity
   - Captures font metadata (fontname, size, colors)

2. **translator.py**: AWS Translate integration 
   - Translation memory caching system
   - Retry logic for failed translations
   - Batch processing support

3. **text_fitter.py**: Advanced text fitting with 4-stage strategy
   - Original size test → Line wrapping → Font scaling → Text truncation
   - Respects word boundaries and maintains readability

4. **overlay_generator.py**: PDF overlay creation with ReportLab
   - Creates white masks over original text
   - Positions translated text with identical coordinates
   - Multi-language font handling (CJK support via Google Fonts)

5. **merger.py**: Final PDF assembly using PyPDF2
   - Merges overlay with original PDF preserving all non-text elements

### Configuration

- **Settings**: `pdf_translator_poc/config/settings.py`
  - AWS configuration (credentials via environment variables)
  - Font paths and language mappings
  - Translation memory and logging paths

### Font Management

- **Google Fonts Integration**: `pdf_translator_poc/src/google_fonts.py`
- **Font Caching**: `pdf_translator_poc/fonts_cache/`
- **System Fonts**: `pdf_translator_poc/fonts/` (includes NotoSans fonts)

## Testing Strategy

The project includes test documents for validation:
- Vietnamese legal circular (simple text layout)
- Production process documents (complex tables and diagrams) 
- BRC standards documents (professional formatting)

Test outputs are saved with timestamps in `test_translation_YYYYMMDD_HHMMSS/` directories.

## Key Features

- **Overlay Approach**: Preserves 100% of original document structure
- **Multi-language Support**: Vietnamese, Japanese, English with appropriate font handling
- **Translation Memory**: Caches translations to avoid re-processing
- **Debug Mode**: Creates intermediate files for inspection (extracted JSON, overlay PDFs)
- **Batch Processing**: Handles documents up to 50 pages efficiently

## AWS Integration

- Uses boto3 for AWS Translate service
- Auto-detects source language or uses specified language codes
- Requires AWS credentials configured via environment variables or AWS CLI