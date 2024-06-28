from typing import Optional


def generate_cache_key(
    cache_prefix: str, item_primary_key: str, cache_postfix: Optional[str] = None
) -> str:
    """Generate a unique cache key with a prefix and key.
    :param cache_prefix: The prefix to use for the cache key, e.g. "feed_item_content"
    :param item_primary_key: The primary key of the item to cache
    :param cache_postfix: Optional postfix to use for the cache key, e.g. "staging"
    :return: The generated cache key
    """
    cache_key = (
        f"{cache_prefix}_{item_primary_key}_{cache_postfix}"
        if cache_postfix
        else f"{cache_prefix}_{item_primary_key}"
    )

    return cache_key
