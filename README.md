# Python interface for code hosting platforms API

It is intended to facilitate research of Open Source projects.
At this point, it is basically functional but is missing:

- tests
- documentation
- good architecture

Feel free to contribute any of those.

### Installation

```bash
pip install --user --upgrade strudel.scraper
``` 


### Usage

```python
import stscraper as scraper
import pandas as pd

gh_api = scraper.GitHubAPI()
# so far only GiHub, Bitbucket and Gitlab are supported
# bb_api = scraper.BitbucketAPI()
# gl_api = scraper.GitLabAPI()

# repo_issues is a generator that can be used
# to instantiate a pandas dataframe
issues = pd.DataFrame(gh_api.repo_issues('cmustrudel/strudel.scraper'))
```



### Settings

GitHub and GitLab APIs limit request rate for unauthenticated requests
(although GitLab limit is much more generous).
There are several ways to set your API keys, listed below in order of priority.

**Important note:** API objects are reused in subsequent calls.
The same keys used to instantiate the first API object will be used by
ALL other instances.

#### Class instantiation:

```python
import stscraper

gh_api = stscraper.GitHubAPI(tokens="comman-separated list of tokens")
```

#### At runtime:

```python
import stscraper
import stutils

# IMPORTANT: do this before creation of the first API object!
stutils.CONFIG['GITHUB_API_TOKENS'] = 'comma-separated list of tokens'
stutils.CONFIG['GITLAB_API_TOKENS'] = 'comma-separated list of tokens'

# any api instance created after this, will use the provided tokens
gh_api = stscraper.GitHubAPI()
```

#### settings file:

```
project root
 \
  |- my_module
  |   \- my_file.py
  |- settings.py
```

```python
# settings.py

GITHUB_API_TOKENS = 'comma-separated list of tokens'
GITLAB_API_TOKENS = 'comma-separated list of tokens'
```

```python
# my_file.py
import stscraper

# keys from settings.py will be reused automatically
gh_api = stscraper.GitHubAPI()
```

#### Environment variable:


```bash
# somewhere in ~/.bashrc
export GITHUB_API_TOKENS='comma-separated list of tokens'
export GITLAB_API_TOKENS='comma-separated list of tokens'
```

```python
# somewhere in the code
import stscraper

# keys from environment variables will be reused automatically
gh_api = stscraper.GitHubAPI()
```


#### Hub config:

If you have [hub](https://github.com/github/hub) installed and everything else
fails, its configuration will be reused for GitHub API.