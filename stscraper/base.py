
from __future__ import absolute_import

import requests

from datetime import datetime
import logging
import random
import re
import six
import time
from typing import Iterable, Iterator, Optional, Tuple, Union
from functools import wraps


class VCSError(requests.HTTPError):
    pass


class RepoDoesNotExist(VCSError):
    pass


class TokenNotReady(VCSError):
    pass


"""
>>> URL_PATTERN.search("github.com/jaraco/jaraco.xkcd").group(0)
'github.com/jaraco/jaraco.xkcd'
>>> URL_PATTERN.search("bitbucket.org/abcd/efgh&klmn").group(0)
'bitbucket.org/abcd/efgh'
"""
PATTERN = r"\b(?:" \
          r"github\.com/[a-zA-Z0-9_.-]+|" \
          r"bitbucket\.org/[a-zA-Z0-9_.-]+|" \
          r"gitlab\.com/(?:[a-zA-Z0-9_.-]+)+|" \
          r"sourceforge\.net/projects" \
          r")/[a-zA-Z0-9_.-]+"
URL_PATTERN = re.compile(PATTERN)


def named_url_pattern(name):
    """ Return project-specific pattern
    This pattern must be consistent with URL_PATTERN
    So far it is only used by pypi.Package to search for URL in code
    """
    return PATTERN.rsplit("/", 1)[0] + name


def parse_url(url):
    # type: (Optional[str]) -> (str, str)
    """Return provider and project id
    >>> parse_url("github.com/user/repo")
    ('github.com', 'user/repo')
    >>> parse_url("bitbucket.org/user/repo")
    ('bitbucket.org', 'user/repo')
    >>> parse_url("gitlab.com/user/repo")
    ('gitlab.com', 'user/repo')
    >>> parse_url("A quick brown fox jumps over the lazy dog")
    (None, None)
    >>> parse_url(None)
    (None, None)
    """
    if url:
        url = url.split("://", 1)[-1]
        provider, rest = url.split("/", 1)
        if provider == "sourceforge.net":
            return provider, rest.rsplit("/", 1)[-1]
        return provider, rest
    return None, None


def json_path(obj, path, raise_on_missing=False):
    """ Get a dict value by the specified path.

    >>> obj = {'author': {'name': 'John'}, 'committer': None,
    ...        'labels': [{'name': 'Bug'}, {'name': 'Good first issue'}]}
    >>> json_path(obj, ('author', 'name'))
    'John'
    >>> json_path(obj, ('committer', 'name')) is None
    True
    >>> json_path(obj, ('committer',)) is None
    True
    >>> json_path(obj, ('labels', ',name'))
    'Bug,Good first issue'
    """
    for chunk in path:
        if chunk.startswith(","):
            obj = ",".join(str(item.get(chunk[1:])) for item in obj)
            # supported only for the last chunk in the path, so break
            break
        if obj is None or chunk not in obj:
            if raise_on_missing:
                raise IndexError('Path does not exist')
            else:
                return None
        obj = obj[chunk]
    return obj


def json_map(mapping, obj):
    """ Get a subset of the obj values by the specified mapping.

    This method is supposed to transform API-specific json (e.g. GitHub)
    result into a smaller subset of fields that can be directly used to
    produce Pandas dataframe

    >>> obj = {'author': {'name': 'John'}, 'committer': None}
    >>> json_map({"author_login": "author__name", 'foo': 'bar'}, obj)
    {'author_login': 'John', 'foo': None}
    """
    return {key: json_path(obj, path.split("__"))
            for key, path in mapping.items()}


# syntax sugar for GET API calls
def api(url, paginate=False, **params):
    def wrapper(func):
        @wraps(func)
        def caller(self, *args):
            formatted_url = url % func(self, *args)
            if paginate:
                return self.request(formatted_url, paginate=True, **params)
            else:
                return next(self.request(formatted_url, **params))
        return caller
    return wrapper


def api_filter(filter_func):
    def wrapper(func):
        @wraps(func)
        def caller(*args):
            for item in func(*args):
                if filter_func(item):
                    yield item
        return caller
    return wrapper


class APIToken(object):
    """ An abstract container for an API token
    """
    # API endpoint
    api_url = None  # type: str

    token = None  # type: str
    # number of seconds before throwing IOError
    timeout = None  # type: int
    # request headers to use
    _headers = {}  # type: dict
    # supported API classes (e.g. core, search etc)
    api_classes = ('core',)  # type: Tuple
    # rate limits for API classes
    limits = None  # type: dict
    session = None  # type: requests.Session

    def __init__(self, token=None, timeout=None):
        self.token = token
        self.timeout = timeout
        self.limits = {api_class: {
            'limit': None,
            'remaining': None,
            'reset_time': None
        } for api_class in self.api_classes}
        self.session = requests.Session()

    @property
    def is_valid(self):
        raise NotImplementedError

    @property
    def user(self):
        """ Get user info of the token owner """
        raise NotImplementedError

    def _update_limits(self, response, url):
        raise NotImplementedError

    def check_limits(self):
        """ Get information about remaining limits on the token.

        Usually this information present in response headers and updated
        automatically (see _update_limits()). This method is intended to
        FORCE to renew this info.

        Some APIs have multiple classes of limits, so it should return a list
        of dictionaries
        { <api_class>: {
                'remaining': remaining number of requests until reset,
                'limit': overall limit,
                'reset_time': unix_timestamp
            },
            ...
         }
        """
        raise NotImplementedError

    @staticmethod
    def api_class(url):
        # type: (str) -> str
        return 'core'

    def when(self, url):
        # type: (str) -> int
        """Check when the specified URL become accessible without blocking

        Returns: unix timestamp
        """
        raise NotImplementedError

    def ready(self, url):
        """ Check if this url can be called without blocking """
        t = self.when(url)
        return not t or t <= time.time()

    def __call__(self, url, method='get', data=None, **params):
        """ Make an API request """
        # TODO: use coroutines, perhaps Tornado (as PY2/3 compatible)

        if not self.ready(url):
            raise TokenNotReady

        r = self.session.request(
            method, self.api_url + url, params=params, data=data,
            headers=self._headers,  timeout=self.timeout)

        self._update_limits(r, url)

        return r

    def __str__(self):
        return self.token or ""


class DummyAPIToken(APIToken):
    """ A dummy token class that does nothing
    APIs that don't have limits should use tokens subclassed from this one
    """

    is_valid = True
    user = 'Anonymous'

    def check_limits(self):
        return self.limits

    def ready(self, url):
        return True

    def when(self, url):
        return None

    def _update_limits(self, response, url):
        pass


class VCSAPI(object):
    _instance = None  # instance of API() for Singleton pattern implementation

    tokens = ()  # type: Tuple[APIToken]
    token_class = DummyAPIToken  # type: type

    status_too_many_requests = ()
    status_not_found = (404, 451)
    status_empty = (409,)
    status_internal_error = (500, 502, 503)
    retries_on_timeout = 5

    def __new__(cls, *args, **kwargs):  # Singleton
        if not isinstance(cls._instance, cls):
            cls._instance = super(VCSAPI, cls).__new__(cls)

        cls._instance.__init__(*args, **kwargs)
        return cls._instance

    def __init__(self, tokens=None, timeout=30):
        # type: (Optional[Union[Iterable,str]], int) -> None
        old_tokens = {str(token) for token in self.tokens}
        if tokens:
            if isinstance(tokens, six.string_types):
                tokens = tokens.split(",")
            new_tokens_instances = [self.token_class(t, timeout=timeout)
                                    for t in set(tokens) - old_tokens]
            self.tokens += tuple(t for t in new_tokens_instances if t.is_valid)
        self.logger = logging.getLogger('scraper.' + self.__class__.__name__)

    def _has_next_page(self, response):
        """ Check if there is a next page to a paginated response """
        raise NotImplementedError

    @staticmethod
    def init_pagination():
        """ Update request params to allow pagination
        Returns: dict of params
        """
        return {'page': 1, 'per_page': 100}

    @staticmethod
    def extract_result(response):
        """ Parse results from the response.
        For most APIs, it is just parsing JSON
        """
        return response.json()

    def iterate_tokens(self, url=""):
        """Infinite generator of tokens, taking care of their availability

        Args:
            url (str): request URL. In some API classes there are multiple rate
                limits handled separately, e.g. GitHub general vs search API.
        Generates:
            (APIToken): a token object
        """
        while True:
            # problem with iterating them in the same order
            # (eg, sorted by expiration): in multithreaded case,
            # all threads are using the same token and GitHub imposes
            # temporary limits. So, random order
            for token in random.sample(self.tokens, len(self.tokens)):
                if not token.ready(url):
                    continue
                yield token

            next_res = min(token.when(url) for token in self.tokens)
            sleep = next_res and int(next_res - time.time()) + 1
            if sleep > 0:
                self.logger.info(
                    "%s: out of keys, resuming in %d minutes, %d seconds",
                    datetime.now().strftime("%H:%M"), *divmod(sleep, 60))
                time.sleep(sleep)
                self.logger.info(".. resumed")

    def request(self, url, method='get', data=None, paginate=False, **params):
        """ Make an API request, taking care of pagination

        Args:
            url (str): request URL
            method (str): HTTP method type
            data (str): API request payload (for POST requests)
            paginate (bool): flag to take care of pagination

        Generates:
            object: parsed object, API-specific
        """
        if paginate:
            params.update(self.init_pagination())

        while True:
            r = self._request(url, method, data, **params)
            if r.status_code in self.status_empty:
                return

            res = self.extract_result(r)
            if paginate:
                for item in res:
                    yield item
                if not res or not self._has_next_page(r):
                    return
                else:
                    params["page"] += 1
                    continue
            else:
                yield res
                return

    def _request(self, url, method='get', data=None, **params):
        """ Make
        Args:
            url (str): request URL
            method (str): HTTP method type
            data (str): API request payload (for POST requests)

        Return:
            requests.Response: raw HTTP response
        """
        timeout_counter = 0
        for token in self.iterate_tokens(url):
            try:
                r = token(url, method=method, data=data, **params)
            except TokenNotReady:
                continue
            except requests.exceptions.RequestException:
                # starting early November, GitHub fails to establish
                # a connection once in a while (bad status line).
                # To account for more general issues like this,
                # TimeoutException was replaced with RequestException
                timeout_counter += 1
                if timeout_counter > self.retries_on_timeout:
                    raise
                continue  # i.e. try again

            if r.status_code in self.status_not_found:  # API v3 only
                raise RepoDoesNotExist(
                    "%s API returned status %s at %s" % (
                        self.__class__.__name__, r.status_code, url))
            elif r.status_code in self.status_internal_error:
                timeout_counter += 1
                if timeout_counter > self.retries_on_timeout:
                    raise requests.exceptions.Timeout("VCS is down")
                time.sleep(2**timeout_counter)
                continue  # i.e. try again
            elif r.status_code in self.status_too_many_requests:
                timeout_counter += 1
                if timeout_counter > self.retries_on_timeout:
                    raise requests.exceptions.Timeout(
                        "Too many requests from the same IP. "
                        "Are you abusing the API?")
                time.sleep(1 << (timeout_counter+1))
                continue

            r.raise_for_status()
            return r

    def all_users(self):
        # type: () -> Iterable[dict]
        """ """
        raise NotImplementedError

    def all_repos(self):
        # type: () -> Iterable[dict]
        """ """
        raise NotImplementedError

    def repo_info(self, repo_slug):
        # type: (Union[str, unicode]) -> Iterator[dict]
        raise NotImplementedError

    def repo_issues(self, repo_slug):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def repo_commits(self, repo_slug):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def repo_pulls(self, repo_slug):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def pull_request_commits(self, repo, pr_id):
        # type: (str, int) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def issue_comments(self, repo, issue_id):
        # type: (str, int) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def review_comments(self, repo, pr_id):
        # type: (str, int) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def user_info(self, user):
        # type: (str) -> dict
        """ """
        raise NotImplementedError

    def user_repos(self, user):
        # type: (str) -> dict
        """Get list of user repositories"""
        raise NotImplementedError

    def user_orgs(self, user):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def org_members(self, org):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def org_repos(self, org):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    @staticmethod
    def project_exists(repo_slug):
        # type: (str) -> bool
        """ """
        raise NotImplementedError
