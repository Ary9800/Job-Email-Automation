import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_ocr_engine = None


def _get_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def extract_text_from_image(image_path: Path) -> str:
    """Offline OCR — works without Ollama. Reads all visible text from screenshot."""
    try:
        engine = _get_engine()
        result, _ = engine(str(image_path))
        if not result:
            return ""
        lines = [item[1] for item in result if item[1]]
        return "\n".join(lines)
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return ""
