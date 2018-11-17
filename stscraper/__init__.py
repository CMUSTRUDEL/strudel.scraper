
from .base import *
from .github import GitHubAPI
from .gitlab import GitLabAPI
from .bitbucket import BitbucketAPI

# make sure to update setup.py
__version__ = '0.2.6'
__author__ = "Marat (@cmu.edu)"

PROVIDERS = {
    "github.com": GitHubAPI,
    # https://developer.atlassian.com/bitbucket/api/2/reference/resource/
    "bitbucket.org": BitbucketAPI,
    # https://docs.gitlab.com/ee/api/
    "gitlab.org": GitLabAPI,
    # https://anypoint.mulesoft.com/apiplatform/sourceforge/
    "sourceforge.net": None,
}


def get_provider(url):
    # type: (str) -> (str, str)
    """ Separate provided URL into parovider and provider-specific project ID
    :param url: url matching URL_PATTERN
    :return: (provider, project_id)

    >>> prov, proj_id = get_provider("github.com/abc/def")
    >>> isinstance(prov, github.GitHubAPI)
    True
    >>> proj_id
    'abc/def'
    >>> prov, proj_id = get_provider("someothersource.com/abc/def")


    """
    provider_name, project_url = parse_url(url)
    provider = PROVIDERS.get(provider_name)
    if provider is None:
        raise NotImplementedError(
            "Provider %s is not supported (yet?)" % provider_name)
    return provider, project_url
