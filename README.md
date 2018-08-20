# Python interface for code hosting platforms API

It is intended to facilitate research of Open Source projects.
At this point, it is basically functional but is missing:

- tests
- documentation
- good architecture

Feel free to contribute any of those.

### Installation

    pip install --user --upgrade strudel.scraper

### Usage

    import stscraper as scraper
    import pandas as pd

    gh_api = scraper.GitHubAPI()
    # so far only GiHub, Bitbucket and Gitlab are supported
    # bb_api = scraper.BitbucketAPI()
    # gl_api = scraper.GitLabAPI()

    # repo_issues is a generator that can be used
    # to instantiate a pandas dataframe
    issues = pd.DataFrame(gh_api.repo_issues('cmustrudel/strudel.scraper'))
