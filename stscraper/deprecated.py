#!/usr/bin/env python
"""
Deprecated tools, mostly serving the purpose of examples
"""


import datetime
import re


def timestamp2str(timestamp):
    return datetime2str(datetime.datetime.fromtimestamp(timestamp))


def datetime2str(dt, fmt="%Y-%m-%d %H:%M"):
    return dt.strftime(fmt)


def utf8fy(string):
    try:
        return string.encode('utf8')
    except UnicodeDecodeError:
        return '*Garbled*'


def commits_gitpython(repo_path, ref='master', short_message=False):
    """ Parse commits from a cloned git repository using gitphython
    This is a rather slow method since gitpython simply parses cli output of
    native git client
    """
    import git

    try:
        repo = git.Repo(repo_path)
    except git.InvalidGitRepositoryError:
        raise ValueError("Not a git repository: %s" % repo_path)

    for commit in repo.iter_commits(ref, max_count=-1):
        # WTF? example:
        # https://github.com/openssl/openssl/commit/c753e71e0a0aea2c540dab96fb02c9c62c6ba7a2
        hasauthor = hasattr(commit, 'author') or None
        hasdate = hasattr(commit, 'committed_date') or None

        message = commit.message.strip()
        if short_message:
            message = message.split("\n", 1)[0].strip()

        yield {
            'sha': commit.hexsha,
            'author_name': hasauthor and utf8fy(commit.author.name),
            'author_email': hasauthor and utf8fy(commit.author.email),
            'authored_date': hasauthor and timestamp2str(commit.authored_date),
            'committer_name': utf8fy(commit.committer.name),
            'committer_email': utf8fy(commit.committer.email),
            'committed_date': hasdate and timestamp2str(commit.committed_date),
            'message': utf8fy(message),
            'parents': commit.parents
        }


def get_repo_name(repo_url):
    assert(repo_url.endswith(".git"))
    chunks = [c for c in re.split("[:/]", repo_url[:-4]) if c]
    org = "" if len(chunks) < 2 else chunks[-2]
    repo = chunks[-1]
    return org, repo


def commits_pygit2(repo_url, remove=True):
    """ Iterate commits using Python libgit2 binding.
    Unlike GitPython, it can clone repository for you and works in the same
    memory space so it is much faster. It is kind of heavy, but can be handy if
    you need to work with repository/commits content (e.g. code analysis)

    :param repo_url Git repository URL (not GitHub URL!).
            Example: git://github.com/user/repo.git
    """
    import os
    import tempfile
    import shutil

    import pygit2
    org, repo_name = get_repo_name(repo_url)
    folder = tempfile.mkdtemp(prefix='_'.join(('ghd', org, repo_name, '')))
    repo = pygit2.clone_repository(repo_url, folder, bare=True)

    try:
        for commit in repo.walk(repo.head.target):
            # http://www.pygit2.org/objects.html#commits
            yield {
                'sha': commit.oid,
                'author_name': commit.author.name,
                'author_email': commit.author.email,
                'committer_name': commit.committer.name,
                'committer_email': commit.committer.email,
                'message': commit.message.strip(),
                'parent_ids': "\n".join(str(pid) for pid in commit.parent_ids),
                'time': commit.commit_time,
            }
    finally:
        if remove:
            os.chdir('/tmp')
            shutil.rmtree(folder)


def issues_PyGithub(github_token, repo_name):
    """ Iterate issues of a GitHub repository using GitHub API v3

    The library used in this method, PyGithub tries to extensively resolve
    attributes which leads to a number of excessive API calls and computation
    overhead. This implementation tries to avoid this, and was replaced by
    local implementation to have uniform interface and get rid of dependency
    """
    # this is not the same module included with scraper.
    # to install, `pip install PyGithub`
    import github

    g = github.Github(github_token)
    repo = g.get_repo(repo_name)
    try:
        id = repo.id
    except github.GithubException:
        raise ValueError("Repository %s does not exist" % repo_name)

    issues = repo.get_issues(state='all')

    # Response example:
    # https://api.github.com/repos/pandas-dev/pandas/issues?page=62
    for issue in issues:
        raw = issue._rawData  # to prevent resolving usernames into objects
        yield {
            'id': int(raw['id']),
            'title': raw['title'],
            'user': raw['user']['login'],
            'labels': ",".join(l['name'] for l in raw['labels']),
            'state': raw['state'],
            'created_at': raw['created_at'],
            'updated_at': raw['updated_at'],
            'closed_at': raw['closed_at'],
            'body': raw['body']
        }
