# Environment configuration examples

These flags are read in the front-end runtime (in browser) and can be injected via your platform or an inline script block.

## Suggested variables
- `APP_DEBUG`: set to `true` to enable console logging in API helpers during debugging; keep `false` in production.
- `API_BASE_URL`: base path for dashboard API calls (default `/api`).
- `FORMS_API_BASE_URL`: base path for marketing form API calls (default `/api/forms`).
- `CSRF_TOKEN_NAME`: selector/name for the CSRF token meta tag (default `csrf-token`).
- `CACHE_TTL_SECONDS`: suggested edge cache TTL for static content (e.g., `300`).

## Example snippet (HTML)
```
<script>
  window.APP_DEBUG = false;
  window.API_BASE_URL = '/api';
  window.FORMS_API_BASE_URL = '/api/forms';
  window.CACHE_TTL_SECONDS = 300;
</script>
```

## Tips
- Never commit real secrets; these values are safe for client-side use only.
- Keep environment values consistent between the website pages and the dashboard pages to avoid mixed endpoints.

