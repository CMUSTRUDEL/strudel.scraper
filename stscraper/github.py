
from __future__ import absolute_import
from __future__ import print_function

import datetime
import json
import os
import warnings

from .base import *
import stutils

# This is a list of preview features
# https://developer.github.com/v3/previews/
# https://developer.github.com/v4/previews
accept_headers = (
    # v3 repository topics
    'application/vnd.github.mercy-preview+json,'
    # v3 reactions
    'application/vnd.github.squirrel-girl-preview,'
    # project event details
    'application/vnd.github.starfox-preview+json,'
    # dependency graph access
    'application/vnd.github.hawkgirl-preview+json'
)


class GitHubAPIToken(APIToken):
    api_url = 'https://api.github.com/'
    api_classes = ('core', 'search')

    _user = None  # cache user
    # dictionaries are mutable. Don't put default headers dict here
    # or it will be shared by all class instances
    _headers = None

    def __init__(self, token=None, timeout=None):
        super(GitHubAPIToken, self).__init__(token, timeout)
        # mercy-preview: repo topics
        # squirrel-girl-preview: issue reactions
        # starfox-preview: issue events
        self._headers = {'Accept': accept_headers}
        if token is not None:
            self.token = token
            self._headers['Authorization'] = 'token ' + token

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

    @property
    def is_valid(self):
        return self.user is not None

    def check_limits(self):
        # regular limits will be updated automatically upon request
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
    """ This is a convenience class to pool GitHub v3 API keys and update their
    limits after every request. Actual work is done by outside classes, such
    as _IssueIterator and _CommitIterator
    """
    token_class = GitHubAPIToken
    base_url = 'https://github.com'
    status_too_many_requests = (403,)

    def __init__(self, tokens=None, timeout=30):
        # Where to look for tokens:
        # strudel config variables
        if not tokens:
            stconfig_tokens = stutils.get_config('GITHUB_API_TOKENS')
            if stconfig_tokens:
                tokens = [token.strip()
                          for token in stconfig_tokens.split(",")
                          if len(token.strip()) == 40]

        # hub configuration: https://hub.github.com/hub.1.html
        # also, used by github actions
        if not tokens:
            token = stutils.get_config('GITHUB_TOKEN')
            if not token and os.path.isfile("~/.config/hub"):
                token = open("~/.config/hub", 'r').read(64)
            if token and len(token.strip()) == 40:
                tokens = [token.strip()]

        if not tokens:
            tokens = [None]
            warnings.warn("No tokens provided. GitHub API will be limited to "
                          "60 requests an hour", Warning)

        super(GitHubAPI, self).__init__(tokens, timeout)

    def _has_next_page(self, response):
        for rel in response.headers.get("Link", "").split(","):
            if rel.rsplit(";", 1)[-1].strip() == 'rel="next"':
                return True
        return False

    # ===================================
    #           API methods
    # ===================================
    @api('users', paginate=True)
    def all_users(self):
        """Get all GitHub users"""
        # https://developer.github.com/v3/users/#get-all-users
        return ()

    @api('repositories', paginate=True)
    def all_repos(self):
        """Get all GitHub repositories"""
        # https://developer.github.com/v3/repos/#list-all-public-repositories
        return ()

    @api('repos/%s')
    def repo_info(self, repo_slug):
        """Get repository info"""
        # https://developer.github.com/v3/repos/#get
        return repo_slug

    @api_filter(lambda issue: 'pull_request' not in issue)
    @api('repos/%s/issues', paginate=True, state='all')
    def repo_issues(self, repo_slug):
        """Get repository issues (not including pull requests)"""
        # https://developer.github.com/v3/issues/#list-issues-for-a-repository
        return repo_slug

    @api('repos/%s/issues/comments', paginate=True)
    def repo_issue_comments(self, repo_slug):
        """ Get all comments in all issues and pull requests,
        both open and closed.
        """
        # https://developer.github.com/v3/issues/comments/#list-comments-in-a-repository
        return repo_slug

    @api('repos/%s/issues/events', paginate=True)
    def repo_issue_events(self, repo_slug):
        """ Get all events in all issues and pull requests,
        both open and closed.
        """
        # https://developer.github.com/v3/issues/events/#list-events-for-a-repository
        return repo_slug

    @api('repos/%s/commits', paginate=True)
    def repo_commits(self, repo_slug):
        """Get all repository commits.
        Note that GitHub API might ignore some merge commits"""
        # https://developer.github.com/v3/repos/commits/#list-commits-on-a-repository
        return repo_slug

    @api('repos/%s/pulls', paginate=True, state='all')
    def repo_pulls(self, repo_slug):
        """Get all repository pull requests.
        Unlike the issues API, this method will return information specific for
        pull requests, like head SHAs and branch names."""
        # https://developer.github.com/v3/pulls/#list-pull-requests
        return repo_slug

    def repo_topics(self, repo_slug):
        """Get a tuple of repository topics.
        Topics are "keywords" assigned by repository owner.

        >>> GitHubAPI().repo_topics('pandas-dev/pandas')
        ('data-analysis', 'pandas', 'flexible', 'alignment', 'python')
        """
        return tuple(
            next(self.request('repos/%s/topics' % repo_slug)).get('names'))

    def repo_labels(self, repo_slug):
        """Get a tuple of repository labels.
        Labels are issue tags used by maintainers

        >>> GitHubAPI().repo_labels('pandas-dev/pandas')[:5]
        ('2/3 Compat', '32bit', 'API - Consistency', 'API Design', 'Admin')
        """
        return tuple(label['name'] for label in
                     self.request('repos/%s/labels' % repo_slug, paginate=True))

    def repo_contributors(self, repo_slug):
        """Get a timeline of up to 100 top project contributors

        Suggested use:

        >>> import pandas as pd
        >>> df = pd.DataFrame(
        ...     GitHubAPI().repo_contributors(repo_slug)).set_index('user')
        >>> df.columns = pd.to_datetime(df.columns, unit='s')
        >>> df
                  2018-08-19  2018-08-26    ...    2020-07-12  2020-07-19
        user                                ...
        user2589           3           0    ...             0           0
        ...
        """
        # https://developer.github.com/v3/repos/statistics/#get-all-contributor-commit-activity
        url = 'repos/%s/stats/contributors' % repo_slug
        for contributor_stats in next(self.request(url)):
            record = {w['w']: w['c'] for w in contributor_stats['weeks']}
            record['user'] = json_path(contributor_stats, ('author', 'login'))
            yield record

    @api('repos/%s/pulls/%d/commits', paginate=True, state='all')
    def pull_request_commits(self, repo, pr_id):
        """Get commits in a pull request.
        `pr_id` is the visible pull request number, not internal GitHub id.
        """
        # https://developer.github.com/v3/issues/comments/#list-comments-on-an-issue
        return repo, pr_id

    @api('repos/%s/issues/%s/comments', paginate=True, state='all')
    def issue_comments(self, repo, issue_id):
        """ Get comments on an issue or a pull request.
        Note that for pull requests this method will return only general
        comments to the pull request, but not review comments related to some
        code. Use review_comments() to get those instead.
        """
        # https://developer.github.com/v3/issues/comments/#list-comments-on-an-issue
        return repo, issue_id

    @api('repos/%s/pulls/%s/comments', paginate=True, state='all')
    def review_comments(self, repo, pr_id):
        """ Get pull request comments related to some code.
        This will not return general comments, see `issue_comments()`
        """
        # https://developer.github.com/v3/pulls/comments/
        return repo, pr_id

    @api('users/%s')
    def user_info(self, username):
        """Get user info - name, location, blog etc."""
        # Docs: https://developer.github.com/v3/users/#response
        return username

    @api('users/%s/repos', paginate=True)
    def user_repos(self, username):
        """Get list of user repositories"""
        # https://developer.github.com/v3/repos/#list-user-repositories
        return username

    @api('users/%s/orgs', paginate=True)
    def user_orgs(self, username):
        """Get user organization membership.
        Usually includes only public memberships, but for yourself you get
        non-public as well."""
        # https://developer.github.com/v3/orgs/#list-user-organizations
        return username

    @api('orgs/%s/members', paginate=True)
    def org_members(self, org):
        """Get public organization members.
        Note that if you are a member of the organization you'll get everybody.
        """
        # https://developer.github.com/v3/orgs/members/#members-list
        return org

    @api('orgs/%s/repos', paginate=True)
    def org_repos(self, org):
        """Get organization repositories"""
        return org

    @api('repos/%s/issues/%d/events', paginate=True)
    def issue_events(self, repo, issue_no):
        """Get issue events.
        This includes state changes, references, labels etc. """
        return repo, issue_no

    # ===================================
    #        Non-API methods
    # ===================================
    @staticmethod
    def project_exists(repo_slug):
        """Check if the project exists.
        This is a slightly cheaper alternative to getting repository info. It
        does not using API keys.
        """
        for i in range(5):
            try:
                return bool(requests.head("https://github.com/" + repo_slug))
            except requests.RequestException:
                time.sleep(2**i)


def parse_graphql_path(query):
    """ Given a query, find object path.
    This naive implementation doesn't account for many quircks in GitHub API.
    In some cases, you still need to specify the path manually
    """
    path = []
    query = re.sub(r'\(.*?\)', '', query.replace('\n', ' ').rstrip(' }'))
    # skip the leading "query(...)" part
    chunks = query.split('{')[1:]
    for chunk in chunks:
        chunk = chunk.strip()
        if chunk in ('nodes', 'edges') or any(c in chunk for c in ' ,}'):
            break
        path.append(chunk)
    return path


class GitHubAPIv4(GitHubAPI):
    """ An interface to GitHub v4 GraphQL API.

    Due to the nature of graphql API, this class does not provide a specific
    set of methods. Instead, you're expected to write your own queries and this
    class will help you with pagination and network timeouts.

    Basic usage:

    >>> api = GitHubAPIv4('github_api_tokens')
    >>> api('''query ($user: String!) {
    ...       user(login:$user) {
    ...         login, name
    ...       }}''', user='user2589')
    {'login': 'user2589', 'name': None}

    >>> list(api('''query ($user: String!, $cursor: String) {
    ...       user(login: $user) {
    ...         followers(first:100, after:$cursor) {
    ...           nodes { login }
    ...           pageInfo{endCursor, hasNextPage}
    ...     }}}''', user='user2589'))
    [{'login': 'ArefMq'},
     # ... more users
     {'login': 'neoascetic'}]

    In the first case, it will return a dictionary of user attributes.
    In the second case, it will return a generator of objects, handling
    pagination transparently.

    It looks a little bit like magic, but it is not. Here is how it works:

    - first, it will parse the query and try to figure out the first object that
        has multiple fields; in the first query, it is `user`. In the second,
        it is `user.followers`.
        The query parser is pretty naive, and is expected to fail on non-trivial
        queries. In this case, you will need to explicitly tell what object you
        want to retrieve. In the example below, we explicitly tell scraper the
        path to the return object in the second positional argument:

        >>> api('...some query..',
        ...     ('repository', 'defaultBranchRef', 'target', 'history'),
        ...     owner='CMUSTRUDEL', repo='strudel.scraper')

    - then, it will check if there is a `pageInfo` object in this object. If it
        is not, it will simply return the content of this object; this is what
        happened with the first query. If there IS a pagination object, it will
        indicate we need pagination, and the content of `nodes` or `edges` will
        be returned instead.

    """

    def v4(self, query, object_path=None, **params):
        """ Make an API v4 request, taking care of pagination

        Args:
            query (str): GraphQL query. If the API request is multipage, it is
                expected that the cursor variable name is "cursor".
            object_path (Tuple[str]): json path to objects to iterate, excluding
                leading "data" part, and the trailing "nodes" when applicable.
                If omitted, will return full "data" content
                Example: ("repository", "issues")
            **params: dictionary of query variables.

        Yields:
            object: parsed object, query-specific

        This method always returns an iterator, so normally you just throw it
        straight into a loop:

        >>> followers = GitHubAPIv4().v4('''
        ...     query ($user: String!, $cursor: String) {
        ...       user(login: $user) {
        ...         followers(first:100, after:$cursor) {
        ...           nodes { login }
        ...           pageInfo{endCursor, hasNextPage}
        ...     }}}''', ("user", "followers"), user=user)
        >>> for follower in followers:
        ...     pass


        However, the method will also return an iterator if the query is
        expected to return a single result. In this case, you need to explicitly
        get the first record, e.g. by calling `next()` on the result:

        >>> user_info = next(self.v4('''
        ...     query ($user: String!) {
        ...       user(login:$user) {
        ...         login, name, avatarUrl, websiteUrl
        ...         company, bio, location, name, twitterUsername, isHireable
        ...         createdAt, updatedAt
        ...         followers{totalCount}
        ...         following {totalCount}
        ...       }}''', ('user',), user=user))

        """
        if object_path is None:
            object_path = parse_graphql_path(query) or ()

        while True:
            payload = json.dumps({'query': query, 'variables': params})

            r = self._request('graphql', 'post', data=payload)
            if r.status_code in self.status_empty:
                return

            res = self.extract_result(r)
            if 'errors' in res or 'data' not in res:
                raise VCSError('API didn\'t return any data:\n' +
                               json.dumps(res, indent=4))
            data = res['data']

            try:
                objects = json_path(data, object_path, raise_on_missing=True)
            except IndexError:
                raise VCSError('Invalid object path "%s" in:\n %s' %
                               (object_path, json.dumps(data)))

            page_info = json_path(objects, ('pageInfo',))
            if page_info is None:
                yield objects
                return
            # This is due to inconsistency in graphql API.
            # In most cases, requests returning lists of objects put them in
            # 'nodes', but in few legacy methods they use 'edges'
            nodes = objects.get('nodes', objects.get('edges'))
            if nodes is None:
                raise EnvironmentError(
                    'Unexpected result format. Please report an issue:\n'
                    'https://github.com/CMUSTRUDEL/strudel.scraper/issues/new')

            for obj in nodes:
                yield obj
            if not json_path(page_info, ('hasNextPage',)):
                break
            # the result is single page, or there are no more pages
            params['cursor'] = json_path(page_info, ('endCursor',))

    def __call__(self, query, object_path=None, **params):
        gen = self.v4(query, object_path, **params)
        if 'pageInfo' in query:
            return iter(gen)
        return next(gen)

    def repo_issues(self, repo_slug, cursor=None):
        owner, repo = repo_slug.split('/')
        return self.v4("""
            query ($owner: String!, $repo: String!, $cursor: String) {
                repository(name: $repo, owner: $owner) {
                    issues (first: 100, after: $cursor,
                      orderBy: {field:CREATED_AT, direction: ASC}) {
                        nodes {author {login}, closed, createdAt,
                               updatedAt, number, title}
                        pageInfo {endCursor, hasNextPage}
            }}}""", ('repository', 'issues'), owner=owner, repo=repo)

    def user_followers(self, user):
        return self.v4("""
            query ($user: String!, $cursor: String) {
              user(login: $user) {
                followers(first:100, after:$cursor) {
                  nodes { login }
                  pageInfo{endCursor, hasNextPage}
            }}}""", ('user', 'followers'), user=user)

    def user_info(self, user):
        return next(self.v4("""
            query ($user: String!) {
              user(login:$user) {
                login, name, avatarUrl, websiteUrl
                company, bio, location, name, twitterUsername, isHireable
                # email  # email requires extra scopes from the API key
                createdAt, updatedAt
                followers{totalCount}
                following {totalCount}
              }}""", ('user',), user=user))

    def repo_commits(self, repo_slug):
        owner, repo = repo_slug.split("/")
        # this is the case when we have to specify object path
        # because of the "... on Commit" syntax
        return self.v4("""
            query ($owner: String!, $repo: String!, $cursor: String) {
            repository(name: $repo, owner: $owner) {
                defaultBranchRef{ target {
                # object(expression: "HEAD") {
                ... on Commit {
                    history (first: 100, after: $cursor) {
                        nodes {sha:oid, author {name, email, user{login}}
                               message, committedDate
                          # normally there is only 1 parent; max observed is 3
                          parents (first:100) {
                            nodes {sha:oid}}
                        }
                        pageInfo {endCursor, hasNextPage}
            }}}}}}""", ('repository', 'defaultBranchRef', 'target', 'history'),
                       owner=owner, repo=repo)

    def repo_stargazers(self, repo_slug):
        owner, repo = repo_slug.split("/")
        return self.v4("""
            query ($owner: String!, $repo: String!, $cursor: String) {
            repository(name: $repo, owner: $owner) {
                stargazers(first: 100, after: $cursor){
                    nodes{ login }
                    pageInfo {endCursor, hasNextPage}
            }}}""", ('repository', 'stargazers'), owner=owner, repo=repo)


def get_limits(tokens=None):
    """Get human-readable rate usage limit.

    Returns a generator of dictionaries with columns:

    """
    api = GitHubAPI(tokens)
    now = datetime.now()

    for i, token in enumerate(api.tokens):
        # if limit is exhausted there is no way to get username
        user = token.user or '<unknown%d>' % i
        values = {'user': user, 'key': token.token}
        token.check_limits()

        for api_class in token.limits:
            next_update = token.limits[api_class]['reset']
            if next_update is None:
                renew = 'never'
            else:
                tdiff = datetime.fromtimestamp(next_update) - now
                renew = '%dm%ds' % divmod(tdiff.seconds, 60)
            values[api_class + '_renews_in'] = renew
            values[api_class + '_limit'] = token.limits[api_class]['limit']
            values[api_class + '_remaining'] = token.limits[api_class]['remaining']

        yield values


def print_limits(argv=None):
    """Check remaining limits of registered GitHub API keys"""

    columns = ('user', 'core_limit', 'core_remaining', 'core_renews_in',
               'search_limit', 'search_remaining', 'search_renews_in',
               'key')

    stats = list(get_limits())

    lens = {column: max(max(len(str(values[column])), len(column))
                        for values in stats)
            for column in columns}

    print('\n', ' '.join(c.ljust(lens[c] + 1, " ") for c in columns))
    for values in stats:
        print(*(str(values[c]).ljust(lens[c] + 1, " ") for c in columns))
