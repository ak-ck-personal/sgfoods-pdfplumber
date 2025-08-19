# settings.py
# Configuration file for AWS and font paths

# AWS Translation Configuration
# AWS_REGION = "us-east-1"
# AWS_ACCESS_KEY_ID = ""  # To be filled by the user
# AWS_SECRET_ACCESS_KEY = ""  # To be filled by the user

# Translation Settings
DEFAULT_SOURCE_LANGUAGE = "auto"  # Auto-detect source language
DEFAULT_TARGET_LANGUAGE = "en"  # Default target language
MAX_RETRIES = 3  # Maximum retry attempts
RETRY_DELAY = 1  # Initial retry delay in seconds
TRANSLATION_LOG_PATH = "translation_log.jsonl"  # Path to log translation pairs

# Font Configuration
FONT_PATHS = {
    "default": "Helvetica",
    "vietnamese": "NotoSans-Regular",
    "cjk": "NotoSansCJK-Regular",
}

# File Paths
TRANSLATION_MEMORY_PATH = "translation_memory.jsonl"
LOG_FILE_PATH = "pdf_translation.log"

# Performance Settings
BATCH_SIZE = 20  # Number of text blocks to process in one batch
