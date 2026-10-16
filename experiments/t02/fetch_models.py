"""Compatibility imports for retained CPU experiments. Setup moved to model_assets."""
from model_assets.fetch_models import LOCK, artifact_path, verify, sha256, download_ranges, fetch

if __name__ == '__main__':
    raise SystemExit('Use the explicit supported setup: docker compose -f compose.models.yaml run --rm model-download')
