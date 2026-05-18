"""
Configuration management for Brand Listener agents.

Loads settings from environment variables, .env file, and provides
default configurations for agents.
"""
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import load_dotenv


# Load environment variables from .env file if present
env_path = Path(__file__).parent.parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    # Try loading from current directory
    load_dotenv()


logger = logging.getLogger(__name__)


def get_env_var(key: str, default: Optional[str] = None) -> str:
    """Get environment variable with logging."""
    value = os.getenv(key, default)
    if value is None:
        logger.warning(f"Environment variable {key} not set, using default: {default}")
    return value


def get_env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning(f"Invalid integer value for {key}: {value}, using default: {default}")
        return default


def get_env_bool(key: str, default: bool) -> bool:
    """Get boolean environment variable."""
    value = os.getenv(key)
    if value is None:
        return default
    value_lower = value.lower()
    if value_lower in ("true", "1", "yes", "y"):
        return True
    elif value_lower in ("false", "0", "no", "n"):
        return False
    else:
        logger.warning(f"Invalid boolean value for {key}: {value}, using default: {default}")
        return default


# FOLO Export Configuration
FOLO_EXPORT_PATH = get_env_var("FOLO_EXPORT_PATH", "./data/exports")
FOLO_EXPORT_PATTERN = get_env_var("FOLO_EXPORT_PATTERN", "*.json")
FOLO_POLLING_INTERVAL_MINUTES = get_env_int("FOLO_POLLING_INTERVAL_MINUTES", 15)
FOLO_UPDATE_LOOKBACK_HOURS = get_env_int("FOLO_UPDATE_LOOKBACK_HOURS", 24)

# OfficialUpdatesAgent Configuration
OFFICIAL_UPDATES_AGENT_MAX_SOURCES = get_env_int("OFFICIAL_UPDATES_AGENT_MAX_SOURCES", 50)
OFFICIAL_UPDATES_AGENT_TIMEOUT_SECONDS = get_env_int("OFFICIAL_UPDATES_AGENT_TIMEOUT_SECONDS", 30)

# API Configuration (optional)
API_HOST = get_env_var("API_HOST", "0.0.0.0")
API_PORT = get_env_int("API_PORT", 8000)
API_RELOAD = get_env_bool("API_RELOAD", True)

# Logging Configuration
LOG_LEVEL = get_env_var("LOG_LEVEL", "INFO")
LOG_FILE = get_env_var("LOG_FILE", "./logs/brand_listener.log")


def get_folo_config() -> Dict[str, Any]:
    """Get FOLO exporter configuration."""
    return {
        "exporter_type": "file",  # Options: "file", "mock"
        "export_path": FOLO_EXPORT_PATH,
        "file_pattern": FOLO_EXPORT_PATTERN,
        "polling_interval_minutes": FOLO_POLLING_INTERVAL_MINUTES,
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS
    }


def get_official_updates_agent_config() -> Dict[str, Any]:
    """Get OfficialUpdatesAgent configuration."""
    return {
        "max_sources": OFFICIAL_UPDATES_AGENT_MAX_SOURCES,
        "timeout_per_source_seconds": OFFICIAL_UPDATES_AGENT_TIMEOUT_SECONDS,
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS,
        "folo_config": get_folo_config()
    }


def get_mock_folo_config() -> Dict[str, Any]:
    """Get mock FOLO configuration for testing."""
    return {
        "exporter_type": "mock",
        "polling_interval_minutes": FOLO_POLLING_INTERVAL_MINUTES,
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS
    }


def get_brand_culture_agent_config() -> Dict[str, Any]:
    """Get BrandCultureListeningAgent configuration."""
    return {
        "max_sources": OFFICIAL_UPDATES_AGENT_MAX_SOURCES,
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS,
        "use_mock": True,
    }


def get_social_media_feedback_agent_config() -> Dict[str, Any]:
    """Get SocialMediaFeedbackAgent configuration."""
    return {
        "max_sources": OFFICIAL_UPDATES_AGENT_MAX_SOURCES,
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS,
        "use_mock": True,
    }


def get_shopping_platform_feedback_agent_config() -> Dict[str, Any]:
    """Get ShoppingPlatformFeedbackAgent configuration."""
    return {
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS,
        "use_mock": True,
    }


def get_other_brand_campaign_analyst_agent_config() -> Dict[str, Any]:
    return {"use_mock": True}


def get_user_feedback_analyst_agent_config() -> Dict[str, Any]:
    return {"use_mock": True}


def get_template_driven_report_agent_config() -> Dict[str, Any]:
    return {"use_mock": True}


def get_task_dispatcher_agent_config() -> Dict[str, Any]:
    return {"use_mock": True}


def get_xhs_agent_config() -> Dict[str, Any]:
    """Get XiaohongshuUpdatesAgent configuration."""
    import json as _json
    api_token = get_env_var("XHS_API_TOKEN", "")
    targets_raw = get_env_var("XHS_MONITOR_TARGETS", "[]")
    try:
        targets = _json.loads(targets_raw)
    except (_json.JSONDecodeError, TypeError):
        logger.warning(f"Invalid XHS_MONITOR_TARGETS JSON, using []")
        targets = []
    search_kw_raw = get_env_var("XHS_SEARCH_KEYWORDS", "[]")
    try:
        search_keywords = _json.loads(search_kw_raw)
    except (_json.JSONDecodeError, TypeError):
        search_keywords = []
    return {
        "xhs_api_token": api_token,
        "xhs_monitor_targets": targets,
        "xhs_min_fans": get_env_int("XHS_MIN_FANS", 0),
        "xhs_search_keywords": search_keywords,
        "xhs_search_num": get_env_int("XHS_SEARCH_NUM", 20),
        "lookback_hours": FOLO_UPDATE_LOOKBACK_HOURS,
    }


def get_api_config() -> Dict[str, Any]:
    """Get API server configuration."""
    return {
        "host": API_HOST,
        "port": API_PORT,
        "reload": API_RELOAD
    }


def get_ocr_agent_config() -> Dict[str, Any]:
    """Get OCR agent configuration."""
    return {
        "ocr_max_images": get_env_int("OCR_MAX_IMAGES", 3),
        "ocr_timeout_seconds": get_env_int("OCR_TIMEOUT_SECONDS", 60),
        "ocr_enabled": get_env_bool("OCR_ENABLED", True),
        "xhs_cookies": get_env_var("XHS_COOKIES", ""),
    }


def setup_logging() -> None:
    """Setup logging configuration."""
    log_level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL
    }

    log_level = log_level_map.get(LOG_LEVEL.upper(), logging.INFO)

    # Create logs directory if needed
    if LOG_FILE:
        log_dir = Path(LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE) if LOG_FILE else logging.StreamHandler(),
            logging.StreamHandler()  # Also log to console
        ]
    )
    logger.info(f"Logging configured with level {LOG_LEVEL}")


# Initialize logging when module is imported
setup_logging()


if __name__ == "__main__":
    # Print current configuration
    print("=== Brand Listener Configuration ===")
    print(f"FOLO Export Path: {FOLO_EXPORT_PATH}")
    print(f"FOLO Export Pattern: {FOLO_EXPORT_PATTERN}")
    print(f"FOLO Polling Interval: {FOLO_POLLING_INTERVAL_MINUTES} minutes")
    print(f"FOLO Lookback Hours: {FOLO_UPDATE_LOOKBACK_HOURS}")
    print(f"Agent Max Sources: {OFFICIAL_UPDATES_AGENT_MAX_SOURCES}")
    print(f"Agent Timeout: {OFFICIAL_UPDATES_AGENT_TIMEOUT_SECONDS} seconds")
    print(f"API Host: {API_HOST}")
    print(f"API Port: {API_PORT}")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"Log File: {LOG_FILE}")