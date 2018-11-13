#!/usr/bin/env python

from __future__ import print_function

import argparse

import stscraper as scraper


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Check remaining limits of registered GitHub API keys")
    args = parser.parse_args()

    columns = ("user", "core_limit", "core_remaining", "core_renews_in",
               "search_limit", "search_remaining", "search_renews_in", "key")

    stats = list(scraper.github.get_limits())

    lens = {column: max(max(len(str(values[column])), len(column))
                        for values in stats)
            for column in columns}

    print(" ".join(c.ljust(lens[c] + 1, " ")for c in columns))
    for values in stats:
        print(" ".join(str(values[c]).ljust(lens[c] + 1, " ") for c in columns))
