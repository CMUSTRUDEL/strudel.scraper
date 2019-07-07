
"""
Standard interface to all supported code hosting platforms.

Two important distinctions comparing to
1. URLs must include the code hosting platform itself, i.e. instead of
    `cmustrudel/strudel.scraper` one should use
    `github.com/cmustrudel/strudel.scraper`.
2. Returned objects are simplified to a common subset of fields
"""

from .base import *
from .github import GitHubAPI
from .gitlab import GitLabAPI
from .bitbucket import BitbucketAPI

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
    """ Separate provided URL into provider and project ID
    :param url: url matching URL_PATTERN
    :return: (provider_cls, project_id)

    >>> prov, proj_id = get_provider("github.com/abc/def")
    >>> isinstance(prov, github.GitHubAPI)
    True
    >>> proj_id
    'abc/def'
    >>> prov, proj_id = get_provider("someothersource.com/abc/def")
    """
    provider_name, project_url = parse_url(url)
    provider_cls = PROVIDERS.get(provider_name)
    if provider_cls is None:
        raise NotImplementedError(
            "Provider %s is not supported (yet?)" % provider_name)
    return provider_cls, project_url


MAPPINGS = {
    'repo_commits': {
        'fields': (
            'sha', 'author', 'author_email', 'author_name', 'authored_at',
            'committer', 'committer_email', 'committed_at', 'comment_count',
            'message', 'verified'),
        'github.com': {
            'sha': 'sha',
            'author': 'author__login',
            'author_email': 'commit__author__email',
            'author_name': 'commit__author__name',
            'authored_at': 'commit__author__date',
            'committer': 'commit__committer__login',
            'committer_email': 'commit__committer__email',
            'committed_at': 'commit__committer__date',
            'comment_count': 'commit__comment_count',
            'message': 'commit__message',
            'verified': 'commit__verification__verified',
            'parents': 'parents__,sha'
        },
    },
    'repo_issues': {
        'fields': (
            'number', 'user', 'role', 'title', 'body', 'assignee', 'id',
            'state', 'created_at', 'updated_at', 'closed_at', 'reactions'),
        'github.com': {
            'number': 'number',
            'user': 'user__login',
            'role': 'author_association',
            'title': 'title',
            'body': 'body',
            'assignee': 'assignee',
            'id': 'id',
            'state': 'state',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'closed_at': 'closed_at',
            'reactions': 'reactions__total_count',
            'pull_request_url': 'pull_request__url',
            'labels': 'labels__,name',
        },
    },
    'repo_pulls': {
        'fields': (
            'number', 'title', 'body', 'state', 'user', 'head',
            'head_branch', 'base', 'base_branch', 'created_at',
            'updated_at', 'closed_at', 'merged_at', 'role'),
        'github.com': {
            'number': 'number',
            'title': 'title',
            'body': 'body',
            'state': 'state',
            'user': 'user__login',
            'head': 'head__repo__full_name',
            'head_branch': 'head__ref',
            'base': 'base__repo__full_name',
            'base_branch': 'base__ref',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'closed_at': 'closed_at',
            'merged_at': 'merged_at',
            'role': 'author_association',
            'labels': 'labels__,name',
        },
    },
    'review_comments': {
        'fields': (  # 'pr_no',
                   'id', 'user', 'created_at', 'updated_at',
                   'body', 'path', 'position', 'role'),
        'github.com': {
            # TODO: 'pr_no': 'pr_no',  # from call params
            'id': 'id',
            'body': 'body',
            'user': 'user__login',
            'role': 'author_association',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'path': 'path',
            'position': 'original_position',
        },
    },
    'issue_comments': {
        'fields': (  # 'issue_no',
                   'id', 'user', 'created_at', 'updated_at',
                   'body', 'role', 'reactions'),
        'github.com': {
            'id': 'id',
            'body': 'body',
            'user': 'user__login',
            'role': 'author_association',
            'created_at': 'created_at',
            'updated_at': 'updated_at',
            'reactions': 'reactions__total_count',
            # TODO: 'issue_no': int(comment['issue_url'].rsplit("/", 1)[-1]),
        }
    },
}


class GenericScraper(object):
    """ Get a small but consistent subset of fields across all VCS providers
    This interface supports the same API as all other VCS providers,
    with one addition: you need to append repository URL
    in front of all other params. For example,

    >>> GitHubAPI().repo_commits("user/repo")

    is equivalent to:

    >>> GenericScraper().repo_commits("https://github.com/user", "user/repo")
    """
    def __getattribute__(self, attr):
        if not hasattr(VCSAPI, attr):
            raise AttributeError("'Scraper' has not attribute '%s'" % attr)
        if attr not in MAPPINGS:
            raise NotImplementedError(
                "Generic API '%s' has not been implemented yet" % attr)
        mappings = MAPPINGS[attr]

        def wrapper(url, *args):
            provider_name, _ = parse_url(url)
            if provider_name not in mappings:
                raise NotImplementedError(
                    "Generic API '%s' has not been implemented for '%s' yet"
                    "" % (attr, provider_name))
            mapping = mappings[provider_name]
            provider_cls, _ = get_provider(url)
            provider = provider_cls()

            for item in getattr(provider, attr)(*args):
                yield json_map(mapping, item)

        return wrapper
