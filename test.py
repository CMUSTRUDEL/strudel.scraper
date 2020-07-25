#!/usr/bin/env python

from typing import Generator
import unittest

import stscraper


class TestBase(unittest.TestCase):

    def test_add_keys(self):
        api = stscraper.VCSAPI('key1,key2,key1')
        self.assertEqual(len(api.tokens), 2)
        api2 = stscraper.VCSAPI('key3,key1,key4')
        self.assertTrue(api2 is api)
        self.assertEqual(len(api.tokens), 4)


class TestGitHub(unittest.TestCase):

    def setUp(self):
        self.api = stscraper.GitHubAPI()
        # choose something that is reasonably large, at least over 1 page
        # of both issues and commits
        self.repo_address = 'pandas-dev/pandas'

    def test_tokens_identity(self):
        # regression test: check tokens don't share identity
        if len(self.api.tokens) < 2:
            return

        limits = {values['user']: values['core_remaining']
                  for values in stscraper.github.get_limits()}

        self.assertEqual(len(self.api.tokens), len(limits),
                         "Number of tokens is greater than number of users")

    def test_check_limits(self):
        limits = stscraper.github.get_limits()
        self.assertIsInstance(limits, Generator)

        limits = list(limits)
        if not limits:
            return
        self.assertIsInstance(limits[0], dict)

    def test_check_print_limits(self):
        import six
        import sys
        old_stdout = sys.stdout
        sys.stdout = six.StringIO()
        try:
            stscraper.github.print_limits()
        finally:
            sys.stdout = old_stdout

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

    def test_repo_info(self):
        info = self.api.repo_info(self.repo_address)
        self.assertIsInstance(info, dict)
        for prop in (
            'id', 'name', 'full_name', 'owner', 'private', 'description',
            'fork', 'language', 'size', 'topics', 'license', 'default_branch',
            'forks_count', 'stargazers_count', 'watchers_count',
            'has_issues', 'has_projects', 'has_wiki', 'has_pages',
            'has_downloads', 'created_at', 'updated_at'
        ):
            self.assertIn(prop, info,
                          "Repository info is expected to have '%s' property,"
                          " but it doesn't" % prop)

    def test_repo_issues(self):
        issues = self.api.repo_issues(self.repo_address)
        self.assertIsInstance(issues, Generator)
        issue = next(issues)
        self._test_issue(issue)
        # issues have this property while pull requests don't
        self.assertIn('comments', issue)

    def test_repo_issue_comments(self):
        comments = self.api.repo_issue_comments(self.repo_address)
        self.assertIsInstance(comments, Generator)
        comment = next(comments)
        self._test_issue_comments(comment)

    def test_repo_issue_events(self):
        events = self.api.repo_issue_events(self.repo_address)
        self.assertIsInstance(events, Generator)
        event = next(events)
        self._test_issue_event(event)

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

    def test_project_exists(self):
        self.assertTrue(self.api.project_exists(self.repo_address))
        self.assertFalse(self.api.project_exists('user2589/nonexistent'))


class TestGitHubv4(unittest.TestCase):

    def setUp(self):
        self.api = stscraper.GitHubAPIv4()
        self.repo_address = 'pandas-dev/pandas'

    def test_user_info(self):
        # Docs: https://developer.github.com/v3/users/#response
        user_info = self.api.user_info('user2589')
        self.assertIsInstance(user_info, dict)
        for prop in ('login', 'name', 'avatarUrl', 'websiteUrl', 'company',
                     'bio', 'location', 'twitterUsername',
                     'isHireable', 'createdAt', 'updatedAt',
                     'followers', 'following'):
            self.assertIn(prop, user_info)

    def test_pagination(self):
        commits = list(self.api.repo_commits('benjaminp/six'))
        self.assertGreater(len(commits), 463)


if __name__ == "__main__":
    unittest.main()
