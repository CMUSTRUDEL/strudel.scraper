
from __future__ import print_function, unicode_literals

import os
import logging
import argparse
import csv
import hashlib

import pandas as pd
from django.core.management.base import BaseCommand

from common import decorators
from common import email_utils as email
from scraper import scraper as scraper

logging.basicConfig()
logger = logging.getLogger('ghd')


class Command(BaseCommand):
    requires_system_checks = False
    help = "Create mapping of GitHub users to their emails for mathching " \
           "StackOverflow records. The result is store in cache folder.\n\n" \
           "This data is generated from commits records, so it is recommnded " \
           "to run ./manage.py scraper_build_cache first."

    def add_arguments(self, parser):
        parser.add_argument('ecosystem', type=str,
                            help='Ecosystem to process, {pypi|npm}')
        parser.add_argument('-o', '--output', default="",
                            help='Output file. Will be extended if already '
                                 'exists')

    def handle(self, *args, **options):
        loglevel = 40 - 10*options['verbosity']
        logger.setLevel(20 if loglevel == 30 else loglevel)

        reader = csv.DictReader(options['input'])

        output = options['output']
        if not output:
            output = os.path.join(
                decorators.get_cache_path('scraper'), "user.emails.csv")
        if os.path.isfile(output):
            users = pd.read_csv(output, index_col=0)
        else:
            users = pd.DataFrame(columns=['uname', 'email_md5'])
            users.index.name = 'email'

        for package in reader:
            logger.info("Processing %s %s", package['name'],
                        package['github_url'])
            if not package['github_url']:
                continue

            commits = scraper._commits(package['github_url'])
            commits = commits.loc[pd.notnull(commits['author_email']) & \
                                  pd.notnull(commits['author'])]
            for _, commit in commits.iterrows():
                if not commit['author'] or not commit['author_email']:
                    continue
                try:
                    email_addr = email.clean(commit['author_email'])
                except ValueError:  # invalid email
                    continue

                if email_addr in users.index:
                    continue

                md5 = hashlib.md5()
                md5.update(email_addr)
                users.loc[email_addr] = {
                    'uname': commit['author'],
                    'email_md5': md5.hexdigest()
                }

        users.to_csv(output)
