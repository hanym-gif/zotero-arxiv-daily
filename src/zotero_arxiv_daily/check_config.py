"""
Configuration completeness checker for zotero-arxiv-daily.

Validates that all required configuration values are set and no placeholder
values (???) remain before running the main workflow.
"""
import sys
import os
import logging
import hydra
from omegaconf import DictConfig, OmegaConf, MissingMandatoryValue
from omegaconf.errors import OmegaConfBaseException
from loguru import logger


def _check_required_env_vars() -> list[str]:
    """Check that required environment variables are set."""
    required_vars = [
        "ZOTERO_ID",
        "ZOTERO_KEY",
        "SENDER",
        "RECEIVER",
        "SENDER_PASSWORD",
        "OPENAI_API_KEY",
        "OPENAI_API_BASE",
    ]
    missing = []
    for var in required_vars:
        value = os.environ.get(var, "")
        if not value:
            missing.append(var)
    return missing


def _collect_missing_fields(cfg: DictConfig, prefix: str = "") -> list[str]:
    """Recursively collect config fields that still hold the ??? placeholder."""
    missing = []
    try:
        items = OmegaConf.to_container(cfg, resolve=False, throw_on_missing=False)
    except OmegaConfBaseException:
        items = {}
    if isinstance(items, dict):
        for key, value in items.items():
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                # Recurse into nested dicts using the original DictConfig
                try:
                    sub_cfg = cfg[key]
                    missing.extend(_collect_missing_fields(sub_cfg, full_key))
                except (KeyError, OmegaConfBaseException):
                    pass
            elif value == "???":
                missing.append(full_key)
    return missing


# config_path is relative to this file's location (src/zotero_arxiv_daily/),
# so ../../config resolves to the repo-root config/ directory — same as main.py.
@hydra.main(version_base=None, config_path="../../config", config_name="default")
def main(config: DictConfig) -> None:
    logger.remove()
    logger.add(sys.stdout, level="INFO", format="<level>{message}</level>")

    has_error = False

    # 1. Check required environment variables
    logger.info("Checking required environment variables...")
    missing_vars = _check_required_env_vars()
    if missing_vars:
        has_error = True
        for var in missing_vars:
            logger.error(f"  ✗ Missing required environment variable: {var}")
    else:
        logger.info("  ✓ All required environment variables are set")

    # 2. Check config for unresolved ??? placeholders
    logger.info("Checking configuration for missing required values...")
    # Suppress hydra/omegaconf noise during resolution attempt
    logging.getLogger("omegaconf").setLevel(logging.CRITICAL)
    try:
        OmegaConf.to_container(config, resolve=True, throw_on_missing=True)
        logger.info("  ✓ All required configuration values are set")
    except MissingMandatoryValue as e:
        has_error = True
        logger.error(f"  ✗ Configuration has missing required value: {e}")
    except OmegaConfBaseException as e:
        # Resolution failed (e.g., env var interpolation error); fall back to
        # scanning for literal ??? placeholders in the unresolved config.
        missing_fields = _collect_missing_fields(config)
        if missing_fields:
            has_error = True
            for field in missing_fields:
                logger.error(f"  ✗ Missing required configuration field: {field}")
        else:
            logger.warning(f"  ! Could not fully resolve configuration: {e}")

    # 3. Final verdict
    if has_error:
        logger.error("\nConfiguration check FAILED. Please fix the issues above before running.")
        sys.exit(1)
    else:
        logger.info("\nConfiguration check PASSED. Your configuration is complete.")


if __name__ == "__main__":
    main()
