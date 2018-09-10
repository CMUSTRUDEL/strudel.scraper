
from .base import *


class BitbucketAPIToken(DummyAPIToken):
    """ A dummy
    Bitbucket isn't using any tokens
    https://confluence.atlassian.com/bitbucket/rate-limits-668173227.html
    """
    api_url = "https://api.bitbucket.org/2.0/"


class BitbucketAPI(VCSAPI):
    token_class = BitbucketAPIToken

    status_not_found = (404, 422, 451)

    def __init__(self, tokens=None, timeout=30):
        super(BitbucketAPI, self).__init__([None], timeout)

    def has_next_page(self, response):
        return 'next' in response.json()

    @staticmethod
    def init_pagination():
        return {'page': 1, 'pagelen': 100}

    @staticmethod
    def extract_result(response, paginate):
        res = response.json()
        if 'error' in res:
            raise VCSError(json_path(res, 'error', 'message'))
        if paginate:
            return res['values']
        return res

    def all_users(self):
        # type: () -> Iterable[dict]
        """ """
        raise NotImplementedError

    def all_repos(self):
        # type: () -> Iterable[dict]
        """ """
        return self.request('repositories', paginate=True)

    def repo_issues(self, repo_name):
        # type: (str) -> Iterable[dict]
        """ """
        return self.request(
            'repositories/%s/issues' % repo_name, paginate=True)

    def repo_commits(self, repo_name):
        # type: (str) -> Iterable[dict]
        """ """
        return self.request(
            'repositories/%s/commits' % repo_name, paginate=True)

    def repo_pulls(self, repo_name):
        # type: (str) -> Iterable[dict]
        """ """
        return self.request('repositories/%s/pullrequests' % repo_name)

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
        return self.request('repositories/' + user)

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
        return bool(requests.head(BitbucketAPIToken.api_url + repo_name))

    @staticmethod
    def canonical_url(project_url):
        # type: (str) -> str
        """ """
        raise NotImplementedError
