"""
Provider Factory to instantiate AI extraction engines dynamically based on configuration.
"""
from backend.app.ai.base_provider import BaseAIProvider
from backend.app.ai.fallback_provider import FallbackDocumentProvider
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def _cfg_get(cfg, key: str, default=None):
    """Read config value whether cfg is a dict (Flask app.config) or a Config class."""
    if isinstance(cfg, dict):
        return cfg.get(key, default)
    return getattr(cfg, key, default)


def get_ai_provider(config=None) -> BaseAIProvider:
    """
    Factory function returning the configured AI extraction provider.
    Supports seamless switching between Azure, OpenAI, Gemini, Claude, and Fallback.
    """
    from backend.app.config import Config
    cfg = config if config is not None else Config

    provider_name = str(_cfg_get(cfg, "AI_PROVIDER", "fallback") or "fallback").strip().lower()
    threshold = float(_cfg_get(cfg, "CONFIDENCE_THRESHOLD", 0.75))

    if provider_name == "azure":
        endpoint = _cfg_get(cfg, "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        key = _cfg_get(cfg, "AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
        if endpoint and key and not key.startswith("your-"):
            try:
                from backend.app.ai.azure_provider import AzureDocumentIntelligenceProvider
                logger.info("Initialized Azure AI Document Intelligence Provider.")
                return AzureDocumentIntelligenceProvider(endpoint=endpoint, api_key=key, confidence_threshold=threshold)
            except Exception as e:
                logger.error(f"Failed to initialize Azure provider ({e}). Falling back.")
        else:
            logger.warning("Azure credentials missing in config. Falling back.")

    elif provider_name in ("vision_openai", "openai"):
        api_key = _cfg_get(cfg, "OPENAI_API_KEY", "")
        model = _cfg_get(cfg, "OPENAI_VISION_MODEL", "gpt-4o")
        if api_key and not api_key.startswith("your-"):
            try:
                from backend.app.ai.vision_provider import VisionAIProvider
                logger.info(f"Initialized OpenAI Vision Provider ({model}).")
                return VisionAIProvider(service="openai", api_key=api_key, model_name=model, confidence_threshold=threshold)
            except Exception as e:
                logger.error(f"Failed to initialize OpenAI provider ({e}). Falling back.")
        else:
            logger.warning("OpenAI API key missing in config. Falling back.")

    elif provider_name in ("vision_gemini", "gemini"):
        api_key = _cfg_get(cfg, "GEMINI_API_KEY", "")
        model = _cfg_get(cfg, "GEMINI_VISION_MODEL", "gemini-3.8-flash")
        if api_key and not api_key.startswith("your-"):
            try:
                from backend.app.ai.vision_provider import VisionAIProvider
                logger.info(f"Initialized Google Gemini Vision Provider ({model}).")
                return VisionAIProvider(service="gemini", api_key=api_key, model_name=model, confidence_threshold=threshold)
            except Exception as e:
                logger.error(f"Failed to initialize Gemini provider ({e}). Falling back.")
        else:
            logger.warning("Gemini API key missing in config. Falling back.")

    logger.info("Using Fallback / Local Document Intelligence Provider.")
    return FallbackDocumentProvider(confidence_threshold=threshold)

