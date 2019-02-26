import warnings

from .base import *
import stutils


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
        if not tokens:
            stconfig_tokens = stutils.get_config("GITLAB_API_TOKENS")
            if stconfig_tokens:
                tokens = [token.strip()
                          for token in stconfig_tokens.split(",")
                          if len(token.strip()) == 20]

        if not tokens:
            tokens = [None]
            warnings.warn("No tokens provided. GitLab API will be limited to "
                          "600 requests per minute", Warning)
        super(GitLabAPI, self).__init__(tokens, timeout)

    def has_next_page(self, response):
        page = response.headers.get('X-Page')
        total_pages = response.headers.get('X-Total-Pages', 0)
        return page is not None and int(page) < int(total_pages)

    @api('users', paginate=True)
    def all_users(self):
        # https://docs.gitlab.com/ee/api/users.html#list-users
        return ()

    @api('projects', paginate=True)
    def all_repos(self):
        # https://docs.gitlab.com/ee/api/projects.html#list-all-projects
        return ()

    @api('projects/%s/issues', paginate=True)
    def repo_issues(self, repo_name):
        # https://docs.gitlab.com/ee/api/issues.html#list-project-issues
        return str_urlencode(repo_name)

    @api('projects/%s/repository/commits', paginate=True)
    def repo_commits(self, repo_name):
        # https://docs.gitlab.com/ee/api/commits.html#list-repository-commits
        return str_urlencode(repo_name)

    @api('projects/%s/merge_requests', paginate=True)
    def repo_pulls(self, repo_name):
        # https://docs.gitlab.com/ee/api/merge_requests.html
        return str_urlencode(repo_name)

    def repo_topics(self, repo_name):
        return next(self.request('projects/%s' % str_urlencode(repo_name))
                    ).get('tag_list', [])

    @api('projects/%s/merge_requests/%s/commits', paginate=True)
    def pull_request_commits(self, repo, pr_iid):
        # https://docs.gitlab.com/ee/api/merge_requests.html#get-single-mr-commits
        return str_urlencode(repo), pr_iid

    @api('projects/%s/issues/%s/notes', paginate=True)
    def issue_comments(self, repo, issue_iid):
        # https://docs.gitlab.com/ee/api/notes.html#list-project-issue-notes
        return str_urlencode(repo), issue_iid

    @api('projects/%s/merge_requests/%s/notes', paginate=True)
    def review_comments(self, repo, pr_iid):
        # https://docs.gitlab.com/ee/api/notes.html#list-all-merge-request-notes
        return str_urlencode(repo), pr_iid

    @api('users/%s')
    def user_info(self, user):
        # https://docs.gitlab.com/ce/api/users.html#single-user
        try:
            return next(self.request('users', username=user))[0]['id']
        except (StopIteration, IndexError):
            raise KeyError("User does not exist")

    @api('users/%s/projects', paginate=True)
    def user_repos(self, user):
        # https://docs.gitlab.com/ee/api/projects.html#list-user-projects
        return user

    @api('users/%s/events', paginate=True)
    def user_events(self, user):
        # https://docs.gitlab.com/ee/api/events.html#get-user-contribution-events
        return user

    def user_orgs(self, user):
        # not available in GitLab API v4
        raise NotImplementedError

    @api('/groups/%s/members/all', paginate=True)
    def org_members(self, org):
        return str_urlencode(org)

    @api('/groups/%s/projects', paginate=True)
    def org_repos(self, org):
        # TODO: recursive groups
        return str_urlencode(org)

    @staticmethod
    def project_exists(repo_name):
        # type: (str) -> bool
        """
        Unlike GitHub, GitLab will return 302 to login page
        for non-existing projects
        """
        return requests.head("https://gitlab.com/" + repo_name
                             ).status_code < 300

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
