# translator.py
# Module for AWS Translate integration

import boto3
import time
import logging
import json
import re
from botocore.exceptions import ClientError
import os
import sys
import hashlib

# Add parent directory to path for imports if needed
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import settings
from config.settings import (
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_TARGET_LANGUAGE,
    MAX_RETRIES,
    RETRY_DELAY,
    TRANSLATION_MEMORY_PATH,
    TRANSLATION_LOG_PATH,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Function to translate text using AWS Translate with retry logic
def check_translation_memory(text_block, target_language):
    """
    Check if a translation already exists in the translation memory.

    Args:
        text_block: Text to translate
        target_language: Target language code

    Returns:
        Cached translation if found, None otherwise
    """
    if not os.path.exists(TRANSLATION_MEMORY_PATH):
        return None

    text_hash = hashlib.md5(text_block.encode("utf-8")).hexdigest()

    try:
        with open(TRANSLATION_MEMORY_PATH, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if (
                        entry.get("text_hash") == text_hash
                        or entry.get("source_text") == text_block
                    ) and entry.get("target_language") == target_language:
                        logger.debug(
                            f"Found cached translation for text: {text_block[:30]}..."
                        )
                        return entry.get("translated_text")
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"Error reading translation memory: {e}")

    return None


def translate_text(
    text_block, target_language, source_language=None, max_retries=MAX_RETRIES, retry_delay=RETRY_DELAY
):
    """
    Translate text using AWS Translate with retry logic.

    Args:
        text_block: Text to translate
        target_language: Target language code (e.g., 'en', 'vi', 'ja')
        source_language: Source language code (None for auto-detection)
        max_retries: Maximum number of retry attempts
        retry_delay: Delay between retries in seconds

    Returns:
        Translated text or original text if translation failed
    """
    if not text_block or text_block.isspace():
        logger.debug("Skipping empty or whitespace-only block")
        return text_block

    # Check if we already have a cached translation
    cached_translation = check_translation_memory(text_block, target_language)
    if cached_translation:
        logger.info("Using cached translation")
        return cached_translation

    # Use the AWS credentials from the local machine's configuration
    try:
        # Create a session using default credentials from AWS CLI configuration
        session = boto3.Session()
        translate_client = session.client("translate")
    except Exception as e:
        logger.error(f"Failed to create AWS Translate client: {e}")
        raise

    for attempt in range(max_retries):
        try:
            response = translate_client.translate_text(
                Text=text_block,
                SourceLanguageCode=source_language or "auto",
                TargetLanguageCode=target_language,
            )

            translated_text = response["TranslatedText"]

            # Log translation pair for debugging
            logger.debug(
                f"Translation successful: {text_block[:50]}... -> {translated_text[:50]}..."
            )

            # Save translation pair to translation memory
            save_to_translation_memory(text_block, translated_text, target_language)

            return translated_text

        except ClientError as e:
            logger.warning(f"Translation attempt {attempt+1}/{max_retries} failed: {e}")

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
                # Increase delay for next retry (exponential backoff)
                retry_delay *= 2
            else:
                logger.error(
                    f"All {max_retries} translation attempts failed for: {text_block[:100]}..."
                )
                return text_block  # Return original text if all retries fail

        except Exception as e:
            logger.error(f"Unexpected error during translation: {e}")
            return text_block  # Return original text on unexpected errors


def save_to_translation_memory(source_text, translated_text, target_language):
    """
    Save translation pair to translation memory for potential reuse.

    Args:
        source_text: Original text
        translated_text: Translated text
        target_language: Target language code
    """
    try:
        # Generate a hash of the source text to use as a unique identifier
        text_hash = hashlib.md5(source_text.encode("utf-8")).hexdigest()

        translation_pair = {
            "source_text": source_text,
            "translated_text": translated_text,
            "target_language": target_language,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "text_hash": text_hash,
        }

        # Create directory if it doesn't exist
        if TRANSLATION_MEMORY_PATH and os.path.dirname(TRANSLATION_MEMORY_PATH):
            os.makedirs(os.path.dirname(TRANSLATION_MEMORY_PATH), exist_ok=True)

        # Append to translation memory file
        with open(TRANSLATION_MEMORY_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(translation_pair, ensure_ascii=False) + "\n")

        # Also log to translation log for debugging
        if TRANSLATION_LOG_PATH:
            os.makedirs(
                (
                    os.path.dirname(TRANSLATION_LOG_PATH)
                    if os.path.dirname(TRANSLATION_LOG_PATH)
                    else "."
                ),
                exist_ok=True,
            )
            with open(TRANSLATION_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(json.dumps(translation_pair, ensure_ascii=False) + "\n")

    except Exception as e:
        logger.error(f"Error saving to translation memory: {e}")


def batch_translate(
    text_blocks, target_language, source_language=None, max_retries=MAX_RETRIES, batch_size=None
):
    """
    Translate multiple text blocks efficiently.

    Args:
        text_blocks: List of text blocks to translate
        target_language: Target language code
        source_language: Source language code (None for auto-detection)
        max_retries: Maximum retry attempts per block
        batch_size: Number of texts to process in each batch (None = use setting)

    Returns:
        List of translated text blocks
    """
    from config.settings import BATCH_SIZE

    if batch_size is None:
        batch_size = BATCH_SIZE

    translated_blocks = []
    success_count = 0
    failure_count = 0
    start_time = time.time()

    # Process texts in batches to avoid overwhelming the API
    for i in range(0, len(text_blocks), batch_size):
        batch = text_blocks[i : i + batch_size]
        logger.info(
            f"Processing batch {i//batch_size + 1}/{(len(text_blocks)-1)//batch_size + 1} ({len(batch)} blocks)"
        )

        for block in batch:
            try:
                translated_block = translate_text(block, target_language, source_language, max_retries)
                translated_blocks.append(translated_block)

                if translated_block != block:  # If translation succeeded
                    success_count += 1
                else:
                    # This could be either an empty block or a failed translation
                    if not block or block.isspace():
                        logger.debug("Empty block skipped")
                    else:
                        failure_count += 1
                        logger.warning(f"Translation failed for block: {block[:50]}...")
            except Exception as e:
                logger.error(f"Error translating block: {e}")
                translated_blocks.append(block)  # Keep original on error
                failure_count += 1

    elapsed_time = time.time() - start_time
    logger.info(
        f"Batch translation completed: {len(translated_blocks)} blocks processed in {elapsed_time:.2f}s"
    )
    logger.info(f"Success: {success_count}, Failures: {failure_count}")

    return translated_blocks


def translate_paragraphs(paragraphs, target_language, source_language=None):
    """
    Translate a list of paragraphs while preserving their metadata.

    Args:
        paragraphs: List of paragraph dictionaries with text and metadata
        target_language: Target language code
        source_language: Source language code (None for auto-detection)

    Returns:
        List of paragraph dictionaries with translated text and preserved metadata
    """
    # Extract just the text content for translation
    text_blocks = [p.get("text", "") for p in paragraphs]

    # Translate all text blocks
    translated_blocks = batch_translate(text_blocks, target_language, source_language)

    # Reconstruct paragraphs with translated text
    translated_paragraphs = []
    for i, paragraph in enumerate(paragraphs):
        # Create a copy to avoid modifying the original
        translated_paragraph = paragraph.copy()
        # Replace the text with the translated version
        translated_paragraph["text"] = translated_blocks[i]
        # Add translation metadata
        translated_paragraph["translated"] = True
        translated_paragraph["target_language"] = target_language
        translated_paragraphs.append(translated_paragraph)

    return translated_paragraphs


def is_translatable_content(text):
    """
    Determine if a text block should be translated or preserved as-is.

    Args:
        text: Text content to analyze

    Returns:
        Boolean indicating if the text should be translated
    """
    # Skip translation for certain patterns

    # URLs and email addresses - simple pattern matching
    url_email_pattern = r"(https?://\S+|www\.\S+|\S+@\S+\.\S+)"
    if re.match(r"^" + url_email_pattern + r"$", text.strip()):
        return False

    # Numbers, dates, codes - if content is primarily numeric
    if re.match(r"^[\d\s\.\,\-\/\:]+$", text.strip()):
        return False

    # Very short text (likely labels or codes)
    if len(text.strip()) < 3:
        return False

    return True
