# Caching strategy

## When to enable caching
- Public website pages such as `app/views/pages/index.liquid` are static; enable caching by default.
- GraphQL page cache helpers at `app/graphql/page_cache` provide update timestamps; use them to decide whether to refresh client caches.
- Authenticated dashboard pages often show user-specific data and should remain uncached unless explicitly safe (e.g., documentation pages).

## How cache invalidation works
- Use `check_records_update_date.graphql` and `check_site_update_date.graphql` to determine if content changed. Compare timestamps and clear or bypass caches when newer than your stored values.
- For client-side caching, store the last-seen timestamp and re-fetch when it differs from the API response.

## Safe defaults
- Default to no caching for any response that includes `current_user` or private profile data.
- Allow caching for static assets (CSS/JS/images) and public GraphQL queries that do not reference `current_user`.

## Enabling caching in environments
- Configure your edge or CDN to cache GET requests to marketing routes and GraphQL page-cache endpoints with short TTLs (e.g., 5–15 minutes).
- Bypass or set `Cache-Control: no-store` on dashboard routes and API responses that carry user data.

