
import warnings

from .base import *

try:
    import settings
except ImportError:
    settings = object()


def str_urlencode(string):
    # TODO: a real encoder
    return string.replace("/", "%2f")


class GitLabAPIToken(APIToken):
    api_url = "https://gitlab.com/api/v4/"

    _user = None  # cache user
    _headers = {}

    def __init__(self, token=None, timeout=None):
        super(GitLabAPIToken, self).__init__(token, timeout)
        if token is not None:
            self.token = token
            self._headers["Private-Token"] = token

    @property
    def user(self):
        if self._user is None:
            try:
                r = self('user')
            except TokenNotReady:
                pass
            else:
                self._user = r.json().get('username', '')
        return self._user

    def check_limits(self):
        # regular limits will be updaated automatically upon request
        # we only need to take care about search limit
        try:
            stats = self('').json()['resources']
        except TokenNotReady:
            stats = {}

        for cls in self.api_classes:
            self.limits[cls] = json_map({
                'remaining': 'remaining',
                'reset': 'reset',
                'limit': 'limit',
            }, stats.get(cls, {}))

        return self.limits

    def when(self, url):
        key = self.api_class(url)
        if self.limits[key]['remaining'] != 0:
            return 0
        return self.limits[key]['reset']

    def _update_limits(self, response, url):
        if 'RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['RateLimit-Remaining'])
            self.limits[self.api_class(url)] = {
                'remaining': remaining,
                'reset': int(response.headers['RateLimit-Reset']),
                'limit': int(response.headers['RateLimit-Limit'])
            }

            if response.status_code == 429 and remaining == 0:
                raise TokenNotReady


class GitLabAPI(VCSAPI):
    """ This is a convenience class to pool GitHub API keys and update their
    limits after every request. Actual work is done by outside classes, such
    as _IssueIterator and _CommitIterator
    """
    token_class = GitLabAPIToken

    status_not_found = (404, 422, 451)

    def __init__(self, tokens=None, timeout=30):
        tokens = tokens or getattr(settings, "SCRAPER_GITLAB_API_TOKENS", [])
        if not tokens:
            tokens = [None]
            warnings.warn("No tokens provided. GitLab API will be limited to "
                          "600 requests per minute", Warning)
        super(GitLabAPI, self).__init__(tokens, timeout)

    def has_next_page(self, response):
        page = response.headers.get('X-Page')
        total_pages = response.headers.get('X-Total-Pages', 0)
        return page is not None and int(page) < int(total_pages)

    def all_users(self):
        for user in self.request('users', paginate=True):
            yield user

    def all_repos(self):
        for repo in self.request('projects', paginate=True):
            yield repo

    def repo_issues(self, repo_name):
        # type: (str) -> Iterable[dict]
        """ """
        raise NotImplementedError

    def repo_commits(self, repo_name):
        url = "projects/%s/repository/commits" % str_urlencode(repo_name)
        for commit in self.request(url, paginate=True):
            yield commit

    def repo_pulls(self, repo_name):
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

    def user_info(self, username):
        # https://docs.gitlab.com/ce/api/users.html#single-user
        return self.request('users/' + username)

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
    def project_exists(repo_name):
        # type: (str) -> bool
        """ """
        return bool(requests.head("https://gitlab.com/" + repo_name))

    @staticmethod
    def canonical_url(project_url):
        # type: (str) -> str
        """
        Case insensitive
        Path can contain only letters, digits, '_', '-' and '.'.
        Cannot start with '-', end in '.git' or end in '.atom'

        Implementation is copied from Github API
        """
        url = project_url.lower()
        for chunk in ("http://", "https://", "gitlab.com"):
            if url.startswith(chunk):
                url = url[len(chunk):]
        if url.endswith("/"):
            url = url[:-1]
        while url.endswith(".git"):
            url = url[:-4]
        return "gitlab.com/" + url

