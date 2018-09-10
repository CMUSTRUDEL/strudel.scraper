
from __future__ import print_function

import numpy as np
import pandas as pd

from stutils import decorators
from stutils import email_utils as email
from . import *

""" First contrib date without MIN_DATE restriction:
> fcd = utils.first_contrib_dates("pypi").dropna()
> df = pd.DataFrame(fcd.rename("fcd"))
> df["url"] = utils.package_urls("pypi")
> df = df.dropna(axis=1).sort_values("fcd")
> df.groupby(df["fcd"].str[:4]).count()

> data = df.iloc[:400]
> def second_month(row):
>     cs = scraper_utils.commit_stats(row["url"])
>     return cs[cs>0].index[1]
> data["second_month"] = data.apply(second_month, axis=1)
> data.groupby(data["second_month"].str[:4]).count()

1970: 3, 1973: 1, 1974: 3, 1997+: 2, 2, 2, 9, 14, 29, 50, 45, 99, 118, ...
looking at their second month of contributions, it is:
nothing before 1997,       1997+: 2, 0, 1, 9, 12, 18, 50, 47, 77, 113,  


So, 1997 looks like a reasonable lower bound.
Only 7 projects (1 commit each) have such commits, so they are safe to ignore
"""

MIN_DATE = "1997"
# username to be used all unidentified users
DEFAULT_USERNAME = "-"

fs_cache = decorators.typed_fs_cache('scraper')

logger = logging.getLogger("ghd.scraper")


def gini(x):
    """ Gini index of a given iterable
    simplified version from https://github.com/oliviaguest/gini

    >>> round(gini([1]*99 + [10**6]), 2)
    0.99
    >>> round(gini([1]*100), 2)
    0.0
    >>> round(gini(range(100)), 2)
    0.34
    """
    n = len(x) * 1.0
    return np.sort(x).dot(2 * np.arange(n) - n + 1) / (n * np.sum(x))


def quantile(data, column, q):
    # type: (pd.DataFrame, str, float) -> pd.DataFrame
    """ Returns number of users responsible for a specific

    :param data: an input pd.Dataframe, e.g. commit_user_stats.reset_index()
        note that without index reset commit_user_stats is a Series
    :param column: a column to aggregate on, e.g. username
    :param q: quantile, e.g. 0.9
    :return: pd.Dataframe aggregated on the specified column
    >>> df = pd.DataFrame({'foo': 1, 'bar': [1,1,1,1,1,1,1,1,1,1]})
    >>> quantile(df, 'foo', 0.5).loc[1, 'bar']
    5
    >>> quantile(df, 'foo', 0.9).loc[1, 'bar']
    9
    """
    # assert column in df.columns  # - doesn't have to be, e.g. multilevel index

    # how it works: sort descending, run cumulative sum and compare to sum
    # number of records under q*sum is exactly what we're looking for
    return data.groupby(column).aggregate(
        lambda x: sum(x.sort_values(ascending=False).cumsum() / x.sum() <= q))


def user_stats(stats, date_field, aggregated_field):
    # type: (pd.DataFrame, str, str) -> pd.Series
    """Helper function for internal use only
    Aggregates specified stats dataframe by month/users
    """
    if stats.empty:
        # a dirty hack to allow further aggregation
        return pd.DataFrame(
            columns=[date_field, 'author', aggregated_field]).set_index(
            [date_field, "author"])[aggregated_field]
    return stats['author'].groupby(
        [stats[date_field].str[:7], stats['author']]).count().rename(
        aggregated_field).astype(np.int)


def zeropad(df, fill_value=0):
    """Ensure monthly index on the passed df, fill in gaps with zeroes
    >>> df = pd.DataFrame([1,1,1], index=["2017-01", "2016-12", "2017-09"])
    >>> zp = zeropad(df)
    >>> zp.index.min()
    '2016-12'
    >>> zp.index.max() >= "2017-12"
    True
    >>> 13 <= len(zp) <= 50
    True
    """
    start = df.index.min()
    if pd.isnull(start):
        idx = []
    else:
        idx = [d.strftime("%Y-%m")
               for d in pd.date_range(start, 'now', freq="M")]
    return df.reindex(idx, fill_value=fill_value)


@fs_cache('raw')
def commits(repo_url):
    # type: (str) -> pd.DataFrame
    """
    convert old cache files:
    find -type f -name '*.csv' -exec rename 's/(?<=\/)commits\./_commits./' {} +

    >>> cs = commits("github.com/benjaminp/six")
    >>> isinstance(cs, pd.DataFrame)
    True
    >>> 450 < len(cs) < 2000  # 454 as of Jan 2018
    True
    >>> len(commits("github.com/user2589/nothingtoseehere"))
    Traceback (most recent call last):
        ...
    RepoDoesNotExist: GH API returned status 404
    """
    provider, project_url = get_provider(repo_url)
    return pd.DataFrame(
        provider.repo_commits(project_url),
        columns=['sha', 'author', 'author_name', 'author_email',
                 'authored_date', 'committed_date', 'parents']
    ).set_index('sha', drop=True)


# @fs_cache('aggregate', 2)
def commit_user_stats(repo_name):
    # type: (str) -> pd.Series
    """
    :param repo_name: str, repo name (e.g. github.com/pandas-dev/pandas
    :return a dataframe indexed on (month, username) with a commits column

    # This repo contains one commit out of order 2005 while repo started in 2016
    >>> cus = commit_user_stats("github.com/django/django")
    >>> isinstance(cus, pd.Series)
    True
    >>> 4100 < len(cus) < 8000  # 4155 unique month/user combinations / Jan 18
    True
    >>> 13 < cus["2017-12"]["sir-sigurd"] < 100 # 22 as of Jan 2018
    True
    >>> "2005" < cus.reset_index()["authored_date"].min() < "2009"
    True
    >>> "2017" < cus.reset_index()["authored_date"].max() < "2022"
    True
    >>> len(cus.reset_index().columns)
    3
    >>> 1 <= len(commit_user_stats("github.com/user2589/schooligan")) < 10  # 1
    True
    """
    stats = commits(repo_name)
    # check for null and empty string is required because of file caching.
    # commits scraped immediately will have empty string, but after save/load
    # it will be converted to NaN by pandas
    min_date = stats.loc[stats["parents"].isnull()
                         | (~stats["parents"].astype(bool)),
                         "authored_date"].min()
    stats = stats[stats["authored_date"] >= min_date]
    stats['author'] = stats['author'].fillna(DEFAULT_USERNAME)
    return user_stats(stats, "authored_date", "commits")


# @fs_cache('aggregate')
def commit_stats(repo_name):
    # type: (str) -> pd.Series
    """Commits aggregated by month

    >>> cs = commit_stats("github.com/django/django")
    >>> isinstance(cs, pd.Series)
    True
    >>> 140 < len(cs) < 240
    True
    >>> 100 < cs["2017-12"] < 200
    True
    """
    return zeropad(commit_user_stats(repo_name).groupby('authored_date').sum())


# @fs_cache('aggregate')
def commit_users(repo_name):
    # type: (str) -> pd.Series
    """Number of contributors by month

    >>> cu = commit_users("github.com/django/django")
    >>> isinstance(cu, pd.Series)
    True
    >>> 140 < len(cu) < 240
    True
    >>> 30 < cu["2017-12"] < 100  # 32
    True
    """
    return commit_user_stats(repo_name).groupby(
        'authored_date').count().rename("users")


# @fs_cache('aggregate')
def commit_gini(repo_name):
    # type: (str) -> pd.Series
    """
    >>> g = commit_gini("github.com/django/django")
    >>> isinstance(g, pd.Series)
    True
    >>> 150 < len(g) < 240
    True
    >>> all(0 <= i <= 1 for i in g)
    True
    """
    return commit_user_stats(repo_name).groupby(
        "authored_date").aggregate(gini).rename("gini")


def contributions_quantile(repo_name, q):
    # type: (str, float) -> pd.Series
    """
    >>> q50 = contributions_quantile("github.com/django/django", 0.5)
    >>> isinstance(q50, pd.Series)
    True
    >>> 140 < len(q50) < 240
    True
    >>> all(q50 >= 0)
    True
    >>> 0 < q50["2017-12"] < 10  # 2
    True
    """
    return quantile(commit_user_stats(repo_name).reset_index(),
                    "authored_date", q)["commits"].rename("q%g" % (q*100))


@fs_cache('raw')
def issues(repo_url):
    # type: (str) -> pd.DataFrame
    """ Get a dataframe with issues

    >>> iss = issues("github.com/benjaminp/six")
    >>> isinstance(iss, pd.DataFrame)
    True
    >>> 180 < len(iss) < 500  # 191 as of Jan 2018
    True
    >>> len(issues("github.com/user2589/minicms"))
    0
    """
    provider, project_url = get_provider(repo_url)
    return pd.DataFrame(
        provider.repo_issues(project_url),
        columns=['number', 'author', 'closed', 'created_at', 'updated_at',
                 'closed_at']).set_index('number', drop=True)


# @fs_cache('aggregate')
def non_dev_issues(repo_name):
    # type: (str) -> pd.DataFrame
    """Same as new_issues with subtracted issues authored by contributors

    >>> ndi = non_dev_issues("github.com/benjaminp/six")
    >>> isinstance(ndi, pd.DataFrame)
    True
    >>> 20 < len(ndi) < len(issues("github.com/benjaminp/six"))  # 23 as of 2018
    True
    """
    cs = commits(repo_name)[['authored_date', 'author']]
    fc = cs.loc[pd.notnull(cs['author'])].groupby(
        'author').min()['authored_date']

    i = issues(repo_name)[['created_at', 'author']].sort_values('created_at')
    i['fc'] = i['author'].map(fc)
    return i.loc[~(i['fc'] < i['created_at']), ['author', 'created_at']]


# @fs_cache('aggregate', 2)
def issue_user_stats(repo_name):
    # type: (str) -> pd.Series
    """
    >>> ius = issue_user_stats("github.com/pandas-dev/pandas")
    >>> isinstance(ius, pd.Series)
    True
    >>> 6000 < len(ius) < 10000  # 6261
    True
    >>> 12 < ius["2017-12"]["toobaz"] < 24  # 13
    True
    >>> (ius > 0).all()
    True
    """
    return user_stats(issues(repo_name), "created_at", "new_issues")


# @fs_cache('aggregate', 2)
def non_dev_issue_user_stats(repo_name):
    return user_stats(non_dev_issues(repo_name), "created_at", "new_issues")


# @fs_cache('aggregate')
def new_issues(repo_name):
    # type: (str) -> pd.Series
    """ New issues aggregated by month

    >>> iss = new_issues("github.com/pandas-dev/pandas")
    >>> isinstance(iss, pd.Series)
    True
    >>> 78 < len(iss) < 100  # 88
    True
    >>> 200 < iss["2017-12"] < 300  # 211
    True
    """
    return issue_user_stats(repo_name).groupby('created_at').sum()


# @fs_cache('aggregate')
def non_dev_issue_stats(repo_name):
    # type: (str) -> pd.Series
    """Same as new_issues, not counting issues submitted by developers
    >>> ndi = non_dev_issue_stats("github.com/pandas-dev/pandas")
    >>> isinstance(ndi, pd.Series)
    True
    >>> 78 < len(ndi) < 180
    True
    >>> (new_issues("github.com/pandas-dev/pandas") >= ndi).all()
    True
    """
    i = non_dev_issues(repo_name)
    return i.groupby(i['created_at'].str[:7]).count()['created_at'].rename(
        "non_dev_issues")


# @fs_cache('aggregate')
def submitters(repo_name):
    # type: (str) -> pd.Series
    """Number of submitters aggregated by month

    >>> ss = submitters("github.com/pandas-dev/pandas")
    >>> isinstance(ss, pd.Series)
    True
    >>> 78 < len(ss) < 180
    True
    >>> all(ss >= 0)
    True
    >>> (new_issues("github.com/pandas-dev/pandas") >= ss).all()
    True
    """
    return issue_user_stats(repo_name).groupby(
        'created_at').count().rename("submitters")


# @fs_cache('aggregate')
def non_dev_submitters(repo_name):
    # type: (str) -> pd.Series
    """New issues aggregated by month
    >>> nds = non_dev_submitters("github.com/pandas-dev/pandas")
    >>> isinstance(nds, pd.Series)
    True
    >>> 80 < len(nds) < 180
    True
    >>> (nds >= 0).all()
    True
    >>> (non_dev_issue_stats("github.com/pandas-dev/pandas") >= nds).all()
    True
    """
    return non_dev_issue_user_stats(repo_name).groupby(
        'created_at').count().rename("non_dev_submitters")


@fs_cache('aggregate')
def closed_issues(repo_name):
    # type: (str) -> pd.Series
    """New issues aggregated by month

    >>> ci = closed_issues("github.com/pandas-dev/pandas")
    >>> isinstance(ci, pd.Series)
    True
    >>> 80 < len(ci) < 150
    True
    >>> 170 < ci["2017-12"] < 1000  # 179
    True
    >>> (ci >= 0).all()
    True
    """
    df = issues(repo_name)
    closed = df.loc[df['closed'], 'closed_at'].astype(object)
    return closed.groupby(closed.str[:7]).count()


@fs_cache('aggregate')
def open_issues(repo_name):
    # type: (str) -> pd.Series
    """Open issues aggregated by month

    >>> oi = open_issues("github.com/pandas-dev/pandas")
    >>> isinstance(oi, pd.Series)
    True
    >>> 80 < len(oi) < 150
    True
    >>> (oi.dropna() >= 0).all()
    True
    """
    submitted = new_issues(repo_name).cumsum()
    closed = closed_issues(repo_name).cumsum()
    res = submitted - closed
    return res.rename("open_issues")


# @fs_cache('aggregate')
def commercial_involvement(url):
    # type: (str) -> pd.Series
    """
    >>> ci = commercial_involvement("github.com/pandas-dev/pandas")
    >>> isinstance(ci, pd.Series)
    True
    >>> 100 < len(ci) < 150
    True
    >>> (0 <= ci).all()
    True
    >>> (1 >= ci).all()
    True
    """
    cs = commits(url)[['authored_date', 'author_email']]
    cs["commercial"] = email.is_commercial_bulk(cs["author_email"])
    stats = cs.groupby(cs['authored_date'].str[:7]).agg(
        {'authored_date': 'count', 'commercial': 'sum'}
    ).rename(columns={'authored_date': "commits"})
    return (stats["commercial"] / stats["commits"]).rename("commercial")


# @fs_cache('aggregate')
def university_involvement(url):
    # type: (str) -> pd.Series
    """
    >>> ui = university_involvement("github.com/pandas-dev/pandas")
    >>> isinstance(ui, pd.Series)
    True
    >>> 100 < len(ui) < 150
    True
    >>> (0 <= ui).all()
    True
    >>> (1 >= ui).all()
    True
    """
    cs = commits(url)[['authored_date', 'author_email']]
    cs["university"] = email.is_university_bulk(cs["author_email"])
    stats = cs.groupby(cs['authored_date'].str[:7]).agg(
        {'authored_date': 'count', 'university': 'sum'}
    ).rename(columns={'authored_date': "commits"})
    return (stats["university"] / stats["commits"]).rename("university")
