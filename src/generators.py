def generate_cache_key(cache_prefix: str, item_primary_key: str) -> str:
    """Generate a unique cache key with a prefix and key.
    :param cache_prefix: The prefix to use for the cache key, e.g. "feed_item_content"
    :param item_primary_key: The primary key of the item to cache
    :return: The generated cache key
    """
    cache_key = (
        f"{cache_prefix}_{item_primary_key}"
        if settings.working_env == Environments.PRODUCTION
        else f"{cache_prefix}_{item_primary_key}_staging"
    )

    return cache_key