# Caching

Seedling caches one page, and you can cache more the same way.

## How a page is cached

A page caches itself with `dynamic_cache` in its front matter. The `key` decides when the
cached copy is replaced: a new key means a fresh render.

```liquid
dynamic_cache:
  layout: true
  key: |-
    {%- assign tables = ["modules/insites_crm/crm_system_field"] -%}
    {%- function key = 'cache/generate_cache_key', tables: tables -%}
    {{ key }}-{{ context.current_user.id }}
```

`cache/generate_cache_key` builds the key from:

- the full URL, so each set of query parameters is cached on its own;
- the newest record in the `tables` you pass, from `page_cache/check_records_update_date`;
- the newest deployed page, layout, partial, asset or form, from `page_cache/check_site_update_date`.

So the cache moves on when a record in one of those tables changes or when you deploy.
Pass the tables whose records the page shows, as `tables:`.

`app/views/pages/account/account_created.html.liquid` is the example in Seedling. Its key
ends with `context.current_user.id`, because the header in its layout shows who is signed in.

## What not to cache

- **Pages that show one user's data.** The dashboard greets the signed-in user by name, so
  it is not cached: a cached copy could show one user's page to another.
- **Anything a form posts to,** and the JSON endpoints under `app/views/pages/api/`.

## While you develop

Leave `dynamic_cache` off while you work on a page. With it on, a change may not show until
the key moves.
