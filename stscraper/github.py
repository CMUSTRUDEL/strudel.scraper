
import json
import warnings

from xml.etree import ElementTree

from .base import *

try:
    import settings
except ImportError:
    settings = object()


def parse_commit(commit):
    github_author = commit['author'] or {}
    commit_author = commit['commit'].get('author') or {}
    return {
        'sha': commit['sha'],
        'author': github_author.get('login'),
        'author_name': commit_author.get('name'),
        'author_email': commit_author.get('email'),
        'authored_date': commit_author.get('date'),
        'message': commit['commit']['message'],
        'committed_date': commit['commit']['committer']['date'],
        'parents': tuple(p['sha'] for p in commit['parents']),
        'verified': commit.get('verification', {}).get('verified')
    }


class GitHubAPIToken(APIToken):
    api_url = "https://api.github.com/"
    api_classes = ('core', 'search')

    _user = None  # cache user
    _headers = {"Accept": "application/vnd.github.mercy-preview+json"}

    def __init__(self, token=None, timeout=None):
        super(GitHubAPIToken, self).__init__(token, timeout)
        if token is not None:
            self.token = token
            self._headers["Authorization"] = "token " + token

    @property
    def user(self):
        if self._user is None:
            try:
                r = self('user')
            except TokenNotReady:
                pass
            else:
                self._user = r.json().get('login', '')
        return self._user

    def check_limits(self):
        # regular limits will be updaated automatically upon request
        # we only need to take care about search limit
        try:
            stats = self('rate_limit').json()['resources']
        except TokenNotReady:
            stats = {}

        for cls in self.api_classes:
            self.limits[cls] = json_map({
                'remaining': 'remaining',
                'reset': 'reset',
                'limit': 'limit',
            }, stats.get(cls, {}))

        return self.limits

    @staticmethod
    def api_class(url):
        return 'search' if url.startswith('search') else 'core'

    def legit(self):
        """ Check if this is a legit key"""
        if self.limits['core']['limit'] is None:
            self.check_limits()
        return self.limits['core']['limit'] < 100

    def when(self, url):
        key = self.api_class(url)
        if self.limits[key]['remaining'] != 0:
            return 0
        return self.limits[key]['reset']

    def _update_limits(self, response, url):
        if 'X-RateLimit-Remaining' in response.headers:
            remaining = int(response.headers['X-RateLimit-Remaining'])
            self.limits[self.api_class(url)] = {
                'remaining': remaining,
                'reset': int(response.headers['X-RateLimit-Reset']),
                'limit': int(response.headers['X-RateLimit-Limit'])
            }

            if response.status_code == 403 and remaining == 0:
                raise TokenNotReady


class GitHubAPI(VCSAPI):
    """ This is a convenience class to pool GitHub API keys and update their
    limits after every request. Actual work is done by outside classes, such
    as _IssueIterator and _CommitIterator
    """
    tokens = None
    token_class = GitHubAPIToken

    user_cookies = None  # cookies for non-API URLs
    user_headers = {   # browser headers for non-API URLs
        'X-Requested-With': 'XMLHttpRequest',
        'Accept-Encoding': "gzip,deflate,br",
        'Accept': "*/*",
        'Origin': 'https://github.com',
        "User-Agent": "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:60.0) "
                      "Gecko/20100101 Firefox/60.0",
        "Host": 'github.com',
        "Referer": "https://github.com",
        "DNT": "1",
        "Accept-Language": 'en-US,en;q=0.5',
        "Connection": "keep-alive",
        "Cache-Control": 'max-age=0',
    }

    def __init__(self, tokens=None, timeout=30):
        tokens = tokens or getattr(settings, "SCRAPER_GITHUB_API_TOKENS", [])
        if not tokens:
            tokens = [None]
            warnings.warn("No tokens provided. GitHub API will be limited to "
                          "60 requests an hour", Warning)

        super(GitHubAPI, self).__init__(tokens, timeout)

    def has_next_page(self, response):
        for rel in response.headers.get("Link", "").split(","):
            if rel.rsplit(";", 1)[-1] == 'rel="next"':
                return True
        return False

    def all_users(self):
        for user in self.request('/users', paginate=True):
            yield user

    def all_repos(self):
        for repo in self.request('/repositories', paginate=True):
            yield repo

    def repo_issues(self, repo_name):
        # type: (str) -> Iterable[dict]
        url = "repos/%s/issues" % repo_name

        data = self.request(url, paginate=True, state='all')

        for issue in data:
            if 'pull_request' not in issue:
                yield {
                    'author': issue['user']['login'],
                    'closed': issue['state'] != "open",
                    'created_at': issue['created_at'],
                    'updated_at': issue['updated_at'],
                    'closed_at': issue['closed_at'],
                    'number': issue['number'],
                    'title': issue['title'],
                    'labels': [l['name'] for l in issue['labels']]
                }

    def repo_commits(self, repo_name):
        url = "repos/%s/commits" % repo_name
        for commit in self.request(url, paginate=True):
            yield parse_commit(commit)

    def repo_pulls(self, repo_name):
        url = "repos/%s/pulls" % repo_name

        for pr in self.request(url, paginate=True, state='all'):
            head = pr.get('head', {})
            head_repo = head and head.get('repo', ())
            base = pr.get('base', {})
            base_repo = base and base.get('repo', ())
            yield {
                'id': int(pr['number']),  # no idea what is in the id field
                'title': pr['title'],
                'body': pr['body'],
                'labels': 'labels' in pr and [l['name'] for l in pr['labels']],
                'created_at': pr['created_at'],
                'updated_at': pr['updated_at'],
                'closed_at': pr['closed_at'],
                'merged_at': pr['merged_at'],
                'author': pr['user']['login'],
                'head': head_repo.get('full_name'),
                'head_branch': head.get('label'),
                'base': base_repo.get('full_name'),
                'base_branch': base.get('label'),
            }

    def repo_topics(self, repo_name):
        return self.request('repos/%s/topics' % repo_name).get('names')

    def pull_request_commits(self, repo, pr_id):
        # type: (str, int) -> Iterable[dict]
        url = "repos/%s/pulls/%d/commits" % (repo, pr_id)

        for commit in self.request(url, paginate=True, state='all'):
            yield parse_commit(commit)

    def issue_comments(self, repo, issue_id):
        """ Return comments on an issue or a pull request
        Note that for pull requests this method will return only general
        comments to the pull request, but not review comments related to
        some code. Use review_comments() to get those instead

        :param repo: str 'owner/repo'
        :param issue_id: int, either an issue or a Pull Request id
        """
        url = "repos/%s/issues/%s/comments" % (repo, issue_id)

        for comment in self.request(url, paginate=True, state='all'):
            yield {
                'body': comment['body'],
                'author': comment['user']['login'],
                'created_at': comment['created_at'],
                'updated_at': comment['updated_at'],
            }

    def review_comments(self, repo, pr_id):
        """ Pull request comments attached to some code
        See also issue_comments()
        """
        url = "repos/%s/pulls/%s/comments" % (repo, pr_id)

        for comment in self.request(url, paginate=True, state='all'):
            yield {
                'id': comment['id'],
                'body': comment['body'],
                'author': comment['user']['login'],
                'created_at': comment['created_at'],
                'updated_at': comment['updated_at'],
                'author_association': comment['author_association']
            }

    def user_info(self, username):
        # Docs: https://developer.github.com/v3/users/#response
        return self.request("users/" + username)

    def user_repos(self, username):
        # type: (str) -> dict
        """Get list of user repositories"""
        return self.request("users/%s/repos" % username, paginate=True)

    def user_orgs(self, username):
        return self.request("users/%s/orgs" % username, paginate=True)

    def org_members(self, org):
        return self.request("orgs/%s/members" % org, paginate=True)

    def org_repos(self, org):
        return self.request("orgs/%s/repos" % org, paginate=True)

    @staticmethod
    def project_exists(repo_name):
        return bool(requests.head("https://github.com/" + repo_name))

    @staticmethod
    def canonical_url(project_url):
        # type: (str) -> str
        """ Normalize URL
        - remove trailing .git  (IMPORTANT)
        - lowercase (API is insensitive to case, but will allow to deduplicate)
        - prepend "github.com"

        :param project_url: str, user_name/repo_name
        :return: github.com/user_name/repo_name with both names normalized

        >>> GitHubAPI.canonical_url("pandas-DEV/pandas")
        'github.com/pandas-dev/pandas'
        >>> GitHubAPI.canonical_url("http://github.com/django/django.git")
        'github.com/django/django'
        >>> GitHubAPI.canonical_url("https://github.com/A/B/")
        'github.com/a/b/'
        """
        url = project_url.lower()
        for chunk in ("http://", "https://", "github.com"):
            if url.startswith(chunk):
                url = url[len(chunk):]
        if url.endswith("/"):
            url = url[:-1]
        while url.endswith(".git"):
            url = url[:-4]
        return "github.com/" + url

    def user_request(self, url):
        """ Make a non-API request
        (it is used to get user activity and repo contributors)
        """
        if self.user_cookies is None:
            self.user_cookies = requests.get("https://github.com").cookies

        r = requests.get(url, cookies=self.user_cookies,
                         headers=self.user_headers)
        r.raise_for_status()
        return r

    def activity(self, repo_name):
        # type: (str) -> dict
        """Get top 100 contributors commit stats by week (non-API method)"""
        return self.user_request(
            "https://github.com/%s/graphs/contributors-data" % repo_name).json()

    def contributions(self, user, year):
        # type: (str, int) -> dict
        """ Get daily user contribution stats (non-API method)"""
        url = "https://github.com/users/%s/contributions?" \
              "from=%d-12-01&to=%d-12-31&full_graph=1" % (user, year, year)
        tree = ElementTree.fromstring(self.user_request(url).text)

        return {rect.attrib.get('data-date'): int(rect.attrib.get('data-count'))
                for rect in tree.iter('rect')
                if rect.attrib.get('class') == 'day'}


class GitHubAPIv4(GitHubAPI):

    def v4(self, query, **params):
        # type: (str) -> dict
        payload = json.dumps({"query": query, "variables": params})
        return self.request("graphql", 'post', data=payload)

    def repo_issues(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          hasIssuesEnabled
            issues (first: 100, after: $cursor,
              orderBy: {field:CREATED_AT, direction: ASC}) {
                nodes {author {login}, closed, createdAt,
                       updatedAt, number, title}
                pageInfo {endCursor, hasNextPage}
        }}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:  # repository is empty, deleted or moved
                break

            for issue in data["issues"]:
                yield {
                    'author': issue['author']['login'],
                    'closed': issue['closed'],
                    'created_at': issue['createdAt'],
                    'updated_at': issue['updatedAt'],
                    'closed_at': None,
                    'number': issue['number'],
                    'title': issue['title']
                }

            cursor = data["issues"]["pageInfo"]["endCursor"]

            if not data["issues"]["pageInfo"]["hasNextPage"]:
                break

    def repo_commits(self, repo_name, cursor=None):
        # type: (str, str) -> Iterable[dict]
        """As of June 2017 GraphQL API does not allow to get commit parents
        Until this issue is fixed this method is only left for a reference
        Please use commits() instead"""
        owner, repo = repo_name.split("/")
        query = """query ($owner: String!, $repo: String!, $cursor: String) {
        repository(name: $repo, owner: $owner) {
          ref(qualifiedName: "master") {
            target { ... on Commit {
              history (first: 100, after: $cursor) {
                nodes {sha:oid, author {name, email, user{login}}
                       message, committedDate}
                pageInfo {endCursor, hasNextPage}
        }}}}}}"""

        while True:
            data = self.v4(query, owner=owner, repo=repo, cursor=cursor
                           )['data']['repository']
            if not data:
                break

            for commit in data["ref"]["target"]["history"]["nodes"]:
                yield {
                    'sha': commit['sha'],
                    'author': commit['author']['user']['login'],
                    'author_name': commit['author']['name'],
                    'author_email': commit['author']['email'],
                    'authored_date': None,
                    'message': commit['message'],
                    'committed_date': commit['committedDate'],
                    'parents': None,
                    'verified': None
                }

            cursor = data["ref"]["target"]["history"]["pageInfo"]["endCursor"]
            if not data["ref"]["target"]["history"]["pageInfo"]["hasNextPage"]:
                break
