"""
FEATURE: SECURE KEY MANAGEMENT
"""

# FLOW:
# - Re-export key loading/auto-generation helpers.
# WHY:
# - Ensures key utilities are discoverable.
# HOW:
# - Re-exports get_aes256_key/ensure_data_encryption_key.

from Security.key_management import get_aes256_key, ensure_data_encryption_key

__all__ = ["get_aes256_key", "ensure_data_encryption_key"]
