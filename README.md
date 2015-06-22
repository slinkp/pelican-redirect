## Pelican-Redirect plugin

### Usage

Drop a source file like `foo.302` anywhere in your article path.
Its content must contain a `location` header, which is the destination to redirect to.  Optionally include a `delay` header, which is the number of seconds to delay before redirect.

### Configuration

In order for it to work, add this to your pelican settings file:

```python
EXTRA_TEMPLATES_PATHS = ['/path/to/pelican-redirect/templates']

REDIRECT_SAVE_AS = PAGE_SAVE_AS

```
