#!/usr/bin/env python

from typing import Generator
import unittest

import stscraper


class TestGitHub(unittest.TestCase):

    def setUp(self):
        self.api = stscraper.GitHubAPI()
        # choose something that is reasonably large, at least over 1 page
        # of both issues and commits
        self.repo_address = 'pandas-dev/pandas'

    def _test_commits(self, commit):
        self.assertIsInstance(commit, dict)
        for prop in ('sha', 'commit', 'author', 'committer', 'parents'):
            self.assertIn(prop, commit,
                          "Commit object is expected to have '%s' property,"
                          " but it doesn't" % prop)
        for prop in ('author', 'committer', 'message', 'comment_count'):
            self.assertIn(prop, commit['commit'],
                          "Commit object is expected to have 'commit.%s' "
                          "property, but it doesn't" % prop)
        for prop1 in ('author', 'committer'):
            for prop2 in ('name', 'email', 'date'):
                self.assertIn(prop2, commit['commit'][prop1])

    def _test_issue(self, issue):
        self.assertIsInstance(issue, dict)
        for prop in ('number', 'state', 'title', 'body', 'user', 'labels',
                     'assignee', 'closed_at', 'created_at',
                     'updated_at', 'author_association', 'locked',
                     # 'reactions'  # omitted if there are no reactions
                     ):
            self.assertIn(prop, issue,
                          "Issue object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_issue_comments(self, comment):
        self.assertIsInstance(comment, dict)
        for prop in ('body', 'user', 'created_at', 'updated_at'):
            self.assertIn(prop, comment,
                          "Issue comment is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_repo(self, repo):
        self.assertIsInstance(repo, dict)
        for prop in ('name', 'full_name', 'fork', 'owner',
                     'has_issues', 'has_projects', 'has_wiki', 'has_pages',
                     'has_downloads', 'license',
                     'stargazers_count', 'forks_count', 'watchers_count',
                     'pushed_at', 'created_at', 'updated_at'):
            self.assertIn(prop, repo,
                          "Repository object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_issue_event(self, event):
        self.assertIsInstance(event, dict)
        for prop in ('actor', 'created_at', 'event', 'url'):
            # might also have 'label'
            self.assertIn(prop, event,
                          "Issue event object is expected to have '%s' property"
                          ", but it doesn't" % prop)

    def test_all_users(self):
        users = self.api.all_users()
        self.assertIsInstance(users, Generator)
        user = next(users)
        self.assertIn('login', user)

    def test_all_repos(self):
        repos = self.api.all_repos()
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        for prop in ('name', 'full_name', 'fork', 'owner'):
            self.assertIn(prop, repo)

    def test_repo_issues(self):
        issues = self.api.repo_issues(self.repo_address)
        self.assertIsInstance(issues, Generator)
        issue = next(issues)
        self._test_issue(issue)
        # issues have this property while pull requests don't
        self.assertIn('comments', issue)

    def test_repo_commits(self):
        commits = self.api.repo_commits(self.repo_address)
        self.assertIsInstance(commits, Generator)
        commit = next(commits)
        self._test_commits(commit)

    def test_repo_pulls(self):
        pulls = self.api.repo_pulls(self.repo_address)
        self.assertIsInstance(pulls, Generator)
        pr = next(pulls)
        self._test_issue(pr)
        for prop in ('merged_at', 'head', 'base'):
            self.assertIn(prop, pr)

    def test_repo_topics(self):
        topics = self.api.repo_topics(self.repo_address)
        self.assertIsInstance(topics, tuple)

    def test_repo_labels(self):
        labels = self.api.repo_labels(self.repo_address)
        self.assertIsInstance(labels, tuple)

    def test_pull_request_commits(self):
        commits = self.api.pull_request_commits(self.repo_address, 22457)
        self.assertIsInstance(commits, Generator)
        commit = next(commits)
        self._test_commits(commit)

    def test_issue_comments(self):
        comments = self.api.issue_comments(self.repo_address, 22473)
        self.assertIsInstance(comments, Generator)
        comment = next(comments)
        self._test_issue_comments(comment)

    def test_review_comments(self):
        comments = self.api.review_comments(self.repo_address, 22457)
        self.assertIsInstance(comments, Generator)
        comment = next(comments)
        self._test_issue_comments(comment)
        for prop in ('diff_hunk', 'commit_id', 'position',
                     'original_position', 'path'):
            self.assertIn(prop, comment)

    def test_user_info(self):
        # Docs: https://developer.github.com/v3/users/#response
        user_info = self.api.user_info('pandas-dev')
        self.assertIsInstance(user_info, dict)
        for prop in ('login', 'type', 'name', 'company', 'blog', 'location',
                     'email', 'bio', 'public_repos', 'followers', 'following',
                     'created_at', 'updated_at'):
            self.assertIn(prop, user_info)

    def test_user_repos(self):
        """Get list of user repositories"""
        repos = self.api.user_repos('pandas-dev')
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        self._test_repo(repo)

    def test_user_orgs(self):
        orgs = self.api.user_orgs('user2589')
        self.assertIsInstance(orgs, Generator)
        org = next(orgs)
        for prop in ('login', 'description'):
            self.assertIn(prop, org)

    def test_org_members(self):
        members = self.api.org_members('cmustrudel')
        self.assertIsInstance(members, Generator)
        user = next(members)
        for prop in ('login', 'type'):
            self.assertIn(prop, user)

    def test_org_repos(self):
        repos = self.api.org_repos('cmustrudel')
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        self._test_repo(repo)

    def test_issue_events(self):
        events = self.api.issue_events('davidmarkclements/0x', 130)
        self.assertIsInstance(events, Generator)
        event = next(events)
        self._test_issue_event(event)

    def test_pagination(self):
        # 464 commits as of Aug 2018
        commits = list(self.api.repo_commits('benjaminp/six'))
        self.assertGreater(len(commits), 463)


class TestGitLab(unittest.TestCase):

    def setUp(self):
        self.api = stscraper.GitLabAPI()
        self.repo_address = 'gitlab-org/gitlab-ce'

    def _test_user(self, user, simple=True):
        self.assertIsInstance(user, dict)
        for prop in ('id', 'username', 'name', 'state', ):
            self.assertIn(prop, user,
                          "User object is expected to have '%s' property,"
                          " but it doesn't" % prop)
        if simple:
            return
        for prop in ('avatar_url', 'created_at', 'bio', 'location', 'skype',
                     'linkedin', 'twitter', 'website_url', 'organization'):
            self.assertIn(prop, user,
                          "User object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_commits(self, commit):
        self.assertIsInstance(commit, dict)
        for prop in ('id', 'short_id', 'title', 'author_name', 'author_email',
                     'authored_date', 'committer_name', 'committer_email',
                     'committed_date', 'created_at', 'message', 'parent_ids'):
            self.assertIn(prop, commit,
                          "Commit object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_issue(self, issue):
        self.assertIsInstance(issue, dict)
        for prop in ('id', 'iid', 'project_id', 'title', 'description', 'state',
                     'created_at', 'updated_at',  # 'closed_by', 'closed_at',
                     'author', 'labels', 'upvotes',  # 'assignees', 'assignee',
                     'downvotes', 'discussion_locked'):
            self.assertIn(prop, issue,
                          "Issue object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_issue_comments(self, comment):
        self.assertIsInstance(comment, dict)
        for prop in ('id', 'body', 'attachment', 'author', 'created_at',
                     'updated_at', 'system', 'noteable_id', 'noteable_type',
                     'noteable_iid'):
            self.assertIn(prop, comment,
                          "Issue comment is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def _test_repo(self, repo):
        self.assertIsInstance(repo, dict)
        for prop in ('id', 'description', 'default_branch', 'tag_list', 'name',
                     'path', 'path_with_namespace', 'forks_count', 'star_count',
                     'created_at', 'last_activity_at', 'issues_enabled',
                     'merge_method', 'creator_id', 'import_status', 'archived',
                     'wiki_enabled', 'snippets_enabled', 'open_issues_count',
                     'merge_requests_enabled',
                     'namespace', 'container_registry_enabled', 'public_jobs'):
            self.assertIn(prop, repo,
                          "Repository object is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def test_all_users(self):
        users = self.api.all_users()
        self.assertIsInstance(users, Generator)
        user = next(users)
        self._test_user(user)

    def test_all_repos(self):
        repos = self.api.all_repos()
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        self._test_repo(repo)

    def test_repo_issues(self):
        issues = self.api.repo_issues(self.repo_address)
        self.assertIsInstance(issues, Generator)
        issue = next(issues)
        self._test_issue(issue)

    def test_repo_commits(self):
        commits = self.api.repo_commits(self.repo_address)
        self.assertIsInstance(commits, Generator)
        commit = next(commits)
        self._test_commits(commit)

    def test_repo_pulls(self):
        pulls = self.api.repo_pulls(self.repo_address)
        self.assertIsInstance(pulls, Generator)
        pr = next(pulls)
        self._test_issue(pr)
        for prop in ('target_branch', 'source_branch', 'source_project_id',
                     'target_project_id', 'work_in_progress', 'merge_status',
                     'merge_commit_sha', 'sha', 'user_notes_count', 'squash',
                     'time_stats', 'approvals_before_merge'):
            self.assertIn(prop, pr,
                          "Merge request is expected to have '%s' property, "
                          "but it doesn't" % prop)

    def test_repo_topics(self):
        topics = self.api.repo_topics(self.repo_address)
        self.assertIsInstance(topics, list)

    def test_pull_request_commits(self):
        # https://gitlab.com/gitlab-org/gitlab-ce/merge_requests/21628
        commits = self.api.pull_request_commits(self.repo_address, 21628)
        self.assertIsInstance(commits, Generator)
        commit = next(commits)
        self._test_commits(commit)

    def test_issue_comments(self):
        # https://gitlab.com/gitlab-org/gitlab-ce/issues/2978
        comments = self.api.issue_comments(self.repo_address, 2978)
        self.assertIsInstance(comments, Generator)
        comment = next(comments)
        self._test_issue_comments(comment)

    def test_review_comments(self):
        # https://gitlab.com/gitlab-org/gitlab-ce/merge_requests/21038
        comments = self.api.review_comments(self.repo_address, 21038)
        self.assertIsInstance(comments, Generator)
        comment = next(comments)
        self._test_issue_comments(comment)

    def test_user_info(self):
        user = self.api.user_info('user2589')
        self._test_user(user, simple=False)

    def test_user_repos(self):
        """Get list of user repositories"""
        repos = self.api.user_repos('user2589')
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        self._test_repo(repo)

    def test_user_orgs(self):
        # not available in GitLab API v4
        with self.assertRaises(NotImplementedError):
            self.api.user_orgs('user2589')

    def test_org_members(self):
        members = self.api.org_members('Inkscape')
        self.assertIsInstance(members, Generator)
        user = next(members)
        self._test_user(user)

    def test_org_repos(self):
        repos = self.api.org_repos('gitlab-org')
        self.assertIsInstance(repos, Generator)
        repo = next(repos)
        self._test_repo(repo)

    def test_pagination(self):
        # 193 commits as of Aug 2018
        commits = list(self.api.repo_commits('user2589/ghd'))
        self.assertGreater(len(commits), 190)


class TestBitBucket(unittest.TestCase):

    def setUp(self):
        self.api = stscraper.BitbucketAPI()
        self.repo_address = 'zzzeek/sqlalchemy'

    # def _test_commits(self, commit):
    #     for prop in ('sha', 'commit', 'author', 'committer', 'parents'):
    #         self.assertIn(prop, commit,
    #                       "Commit object is expected to have '%s' property,"
    #                       " but it doesn't" % prop)
    #     for prop in ('author', 'committer', 'message', 'comment_count'):
    #         self.assertIn(prop, commit['commit'],
    #                       "Commit object is expected to have 'commit.%s' "
    #                       "property, but it doesn't" % prop)
    #     for prop1 in ('author', 'committer'):
    #         for prop2 in ('name', 'email', 'date'):
    #             self.assertIn(prop2, commit['commit'][prop1])
    #
    # def _test_issue(self, issue):
    #     for prop in ('number', 'state', 'title', 'body', 'user', 'labels',
    #                  'assignee', 'closed_at', 'created_at',
    #                  'updated_at', 'author_association', 'locked'):
    #         self.assertIn(prop, issue,
    #                       "Issue object is expected to have '%s' property,"
    #                       " but it doesn't" % prop)
    #
    # def _test_issue_comments(self, comment):
    #     for prop in ('body', 'user', 'created_at', 'updated_at'):
    #         self.assertIn(prop, comment,
    #                       "Issue comment is expected to have '%s' property,"
    #                       " but it doesn't" % prop)
    #
    # def _test_repo(self, repo):
    #     for prop in ('name', 'full_name', 'fork', 'owner',
    #                  'has_issues', 'has_projects', 'has_wiki', 'has_pages',
    #                  'has_downloads', 'license',
    #                  'stargazers_count', 'forks_count', 'watchers_count',
    #                  'pushed_at', 'created_at', 'updated_at'):
    #         self.assertIn(prop, repo,
    #                       "Repository object is expected to have '%s' property,"
    #                       " but it doesn't" % prop)
    #
    # def test_all_users(self):
    #     users = self.api.all_users()
    #     self.assertIsInstance(users, Generator)
    #     user = next(users)
    #     self.assertIn('login', user)
    #
    # def test_all_repos(self):
    #     repos = self.api.all_repos()
    #     self.assertIsInstance(repos, Generator)
    #     repo = next(repos)
    #     for prop in ('name', 'full_name', 'fork', 'owner'):
    #         self.assertIn(prop, repo)
    #
    # def test_repo_issues(self):
    #     issues = self.api.repo_issues(self.repo_address)
    #     self.assertIsInstance(issues, Generator)
    #     issue = next(issues)
    #     self._test_issue(issue)
    #     # issues have this property while pull requests don't
    #     self.assertIn('comments', issue)
    #
    # def test_repo_commits(self):
    #     commits = self.api.repo_commits(self.repo_address)
    #     self.assertIsInstance(commits, Generator)
    #     commit = next(commits)
    #     self._test_commits(commit)
    #
    # def test_repo_pulls(self):
    #     pulls = self.api.repo_pulls(self.repo_address)
    #     self.assertIsInstance(pulls, Generator)
    #     pr = next(pulls)
    #     self._test_issue(pr)
    #     for prop in ('merged_at', 'head', 'base'):
    #         self.assertIn(prop, pr)
    #
    # def test_repo_topics(self):
    #     topics = self.api.repo_topics(self.repo_address)
    #     self.assertIsInstance(topics, list)
    #
    # def test_pull_request_commits(self):
    #     commits = self.api.pull_request_commits(self.repo_address, 22457)
    #     self.assertIsInstance(commits, Generator)
    #     commit = next(commits)
    #     self._test_commits(commit)
    #
    # def test_issue_comments(self):
    #     comments = self.api.issue_comments(self.repo_address, 22473)
    #     self.assertIsInstance(comments, Generator)
    #     comment = next(comments)
    #     self._test_issue_comments(comment)
    #
    # def test_review_comments(self):
    #     comments = self.api.review_comments(self.repo_address, 22457)
    #     self.assertIsInstance(comments, Generator)
    #     comment = next(comments)
    #     self._test_issue_comments(comment)
    #     for prop in ('diff_hunk', 'commit_id', 'position',
    #                  'original_position', 'path'):
    #         self.assertIn(prop, comment)
    #
    # def test_user_info(self):
    #     # Docs: https://developer.github.com/v3/users/#response
    #     user_info = self.api.user_info('pandas-dev')
    #     self.assertIsInstance(user_info, dict)
    #     for prop in ('login', 'type', 'name', 'company', 'blog', 'location',
    #                  'email', 'bio', 'public_repos', 'followers', 'following',
    #                  'created_at', 'updated_at'):
    #         self.assertIn(prop, user_info)
    #
    # def test_user_repos(self):
    #     """Get list of user repositories"""
    #     repos = self.api.user_repos('pandas-dev')
    #     self.assertIsInstance(repos, Generator)
    #     repo = next(repos)
    #     self._test_repo(repo)
    #
    # def test_user_orgs(self):
    #     orgs = self.api.user_orgs('user2589')
    #     self.assertIsInstance(orgs, Generator)
    #     org = next(orgs)
    #     for prop in ('login', 'description'):
    #         self.assertIn(prop, org)
    #
    # def test_org_members(self):
    #     members = self.api.org_members('cmustrudel')
    #     self.assertIsInstance(members, Generator)
    #     user = next(members)
    #     for prop in ('login', 'type'):
    #         self.assertIn(prop, user)
    #
    # def test_org_repos(self):
    #     repos = self.api.org_repos('cmustrudel')
    #     self.assertIsInstance(repos, Generator)
    #     repo = next(repos)
    #     self._test_repo(repo)
    #
    # def test_pagination(self):
    #     # 464 commits as of Aug 2018
    #     commits = list(self.api.repo_commits('benjaminp/six'))
    #     self.assertGreater(len(commits), 463)


class TestGeneric(unittest.TestCase):

    def test_(self):
        pass


class TestStats(unittest.TestCase):

    def test_(self):
        pass


if __name__ == "__main__":
    unittest.main()
