
Reference
===========

.. toctree::
   :maxdepth: 2

.. py:module:: stscraper

`stscraper` is a Python interface for GitHub API

Key features:

- utilize multiple API keys to speed up scraping
- transparently handle pagination and minor network errors

Installation
------------

.. code-block:: bash

    pip install --user --upgrade strudel.scraper


Usage
-----

The main way to use this module is through :py:class:`GitHubAPI` objects.

.. code-block::

    import stscraper as scraper
    import pandas as pd

    gh_api = scraper.GitHubAPI("token1,token2,...")

    # repo_issues is a generator that can be used
    # to instantiate a pandas dataframe
    issues = pd.DataFrame(gh_api.repo_issues('cmustrudel/strudel.scraper'))

Tokens can be provided either at class instantiation or through an environment
variable:

.. code-block:: bash

    # somewhere in ~/.bashrc
    export GITHUB_API_TOKENS='comma-separated list of tokens'

.. code-block::

    # later, in some Python file:
    gh_api = scraper.GitHubAPI()  # tokens from the environment var will be used

If no keys were passed at class instantiation and `GITLAB_API_TOKENS`
environment variable is not defined, `stscraper` will also check `GITHUB_TOKEN`
environment variable. This variable is created by GitHub actions runner and also
used by `hub <https://github.com/github/hub)>`_ utility.

REST (v3) API
-------------
.. autoclass:: GitHubAPI
    :members:
    :exclude-members: token_class

GraphQL (v4) API
----------------

.. autoclass:: GitHubAPIv4
    :members:

