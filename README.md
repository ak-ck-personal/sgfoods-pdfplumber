# SGFoods PDF Translator

SGFoods is a Python-based tool designed to translate PDF documents while preserving their original formatting, including tables, images, and layouts. The tool uses AWS Translate and an overlay approach to replace text content with translations.

## Features

- **Overlay Approach**: Maintains the original document structure.
- **Multi-language Support**: Supports Vietnamese, Japanese, and English with appropriate font handling.
- **Translation Memory**: Caches translations to avoid re-processing.
- **Debug Mode**: Generates intermediate files for inspection (e.g., extracted JSON, overlay PDFs).
- **Batch Processing**: Efficiently handles documents up to 50 pages.

## Installation

1. Clone the repository:

   ```bash
   git clone https://github.com/ak-ck-personal/sgfoods-pdfplumber.git
   ```

2. Navigate to the project directory:

   ```bash
   cd sgfoods-pdfplumber
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Virtual Environment

To set up a virtual environment for the project:

1. Create a virtual environment:

   ```bash
   python -m venv pdf_translator_env
   ```

2. Activate the virtual environment:

   - On Windows:
     ```bash
     pdf_translator_env\Scripts\activate
     ```
   - On macOS/Linux:
     ```bash
     source pdf_translator_env/bin/activate
     ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the main translation pipeline test:

```bash
python pdf_translator_poc/tests/test_translation_pipeline.py <pdf_path> [-t target_language] [--debug]
```

### Examples:

```bash
python pdf_translator_poc/tests/test_translation_pipeline.py documents/circular.pdf -t en
python pdf_translator_poc/tests/test_translation_pipeline.py documents/circular.pdf -t ja --debug
```

## Project Structure

- **Core Modules**:

  - `extractor.py`: Extracts text and font metadata from PDFs.
  - `translator.py`: Integrates with AWS Translate for text translation.
  - `text_fitter.py`: Fits translated text into the original layout.
  - `overlay_generator.py`: Creates overlays with translated text.
  - `merger.py`: Merges overlays with the original PDF.

- **Configuration**:

  - `config/settings.py`: Contains AWS and font settings.

- **Fonts**:
  - `fonts_cache/`: Cached Google Fonts.
  - `fonts/`: System fonts (e.g., NotoSans).

## Testing

Test documents are included for validation:

- Vietnamese legal circulars.
- Production process documents.
- BRC standards documents.

Test outputs are saved in timestamped directories (e.g., `test_translation_YYYYMMDD_HHMMSS/`).

## AWS Integration

- Uses `boto3` for AWS Translate.
- Auto-detects source language or uses specified language codes.
- Requires AWS credentials configured via environment variables or AWS CLI.

## License

This project is licensed under the MIT License.
