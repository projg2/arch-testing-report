#!/usr/bin/env python

import argparse
import logging
import operator
from datetime import datetime, timedelta
from functools import cached_property
from pathlib import Path
from typing import Any

import jinja2
import requests

class Bugzilla:
    ARCHES = ('alpha', 'amd64', 'arm', 'arm64', 'hppa', 'ia64', 'loong', 'mips', 'ppc', 'ppc64', 'riscv', 's390', 'sparc', 'x86')
    DEVBOXES = frozenset({'amd64', 'arm', 'arm64', 'hppa', 'ia64', 'ppc', 'ppc64', 's390', 'sparc', 'x86'})
    ARCHES_EMAILS = frozenset(f'{arch}@gentoo.org' for arch in ARCHES)

    inactive_threshold = 14
    inactive_date = datetime.utcnow() - timedelta(days=inactive_threshold)

    def __init__(self):
        self.api_key = self.__read_api_key()
        self.session = requests.Session()

    @staticmethod
    def __read_api_key():
        try:
            with open('bugs.key', encoding='utf-8') as f:
                return f.read().strip()
        except Exception:
            return None

    def get(self, endpoint, **kwargs):
        kwargs.setdefault('Bugzilla_api_key', [self.api_key])
        return self.session.get(f'https://bugs.gentoo.org/rest/{endpoint}',
                                params=kwargs,
                                timeout=30).json()

    def transform_bug(self, bug: dict[str, Any]):
        bug = dict(bug)
        bug['atoms'] = bug['cf_stabilisation_atoms'].split('\r\n')
        bug['creation_time'] = datetime.fromisoformat(
            bug['creation_time'].rstrip('Z'))
        bug['last_change_time'] = datetime.fromisoformat(
            bug['last_change_time'].rstrip('Z'))
        bug['depends_on'] = frozenset(bug['depends_on'])
        bug['arches'] = sorted(s.removesuffix('@gentoo.org') for s in self.ARCHES_EMAILS.intersection(bug.get("cc", ())))
        return bug

    @cached_property
    def arches_bugs(self) -> tuple[dict[str, Any], ...]:
        logging.info('Fetching all arches bugs')
        json = self.get('bug',
                        resolution=['---'],
                        cc=[self.ARCHES_EMAILS],
                        f1=['flagtypes.name'],
                        o1=['anywords'],
                        v1=['sanity-check+'],)
        return tuple(map(self.transform_bug, json['bugs']))

    @cached_property
    def dependencies(self) -> dict[int, dict[str, Any]]:
        depends_on = set().union(*(bug['depends_on'] for bug in self.arches_bugs))
        logging.info('Fetching depends on bugs')
        json = self.get('bug',
                        id=list(depends_on),
                        resolution=['---'],)
        return {
            bug['id']: self.transform_bug(bug)
            for bug in json['bugs']
        }

    @cached_property
    def last_arch(self):
        return {
            arch: tuple(
                bug for bug in self.arches_bugs
                if self.ARCHES_EMAILS.intersection(bug.get("cc", ())) == {f'{arch}@gentoo.org'}
            ) for arch in self.ARCHES
        }

    @cached_property
    def security_bugs(self):
        return tuple(
            bug for bug in self.arches_bugs
            if 'SECURITY' in bug['keywords']
        )

    @cached_property
    def inactive_bugs(self):
        return tuple(
            bug for bug in self.arches_bugs
            if bug['last_change_time'] < self.inactive_date and not bug['depends_on'].intersection(self.dependencies.keys())
        )

    @cached_property
    def for_devboxes(self):
        return tuple(
            bug for bug in self.arches_bugs
            if self.DEVBOXES.intersection(bug['arches'])
        )

    @cached_property
    def arch_stats(self):
        arches = {arch: (0, ) * 4 for arch in self.ARCHES}
        for bug in self.arches_bugs:
            is_keywording = bug['component'] == 'Keywording'
            vec = (
                1, # total
                int(not is_keywording), # stablereq
                int(is_keywording), # keywording
                int(bool(bug['depends_on'].intersection(self.dependencies.keys()))), #blocked
            )
            for arch in bug['arches']:
                arches[arch] = tuple(map(operator.add, arches[arch], vec))
        return arches

    @cached_property
    def bad_sanity(self) -> tuple[dict[str, Any], ...]:
        logging.info('Fetching all bad sanity bugs')
        json = self.get('bug',
                        resolution=['---'],
                        f1=['flagtypes.name'],
                        o1=['anywords'],
                        v1=['sanity-check-'],)
        return tuple(map(self.transform_bug, json['bugs']))

    @cached_property
    def waiting_maintainers(self):
        logging.info('Fetching all bugs waiting for maintainers')
        json = self.get('bug',
                        resolution=['---'],
                        component=['Keywording', 'Stabilization'],
                        f1=['flagtypes.name'],
                        o1=['anywords'],
                        v1=['sanity-check+'],
                        keywords=['CC-ARCHES'],
                        keywords_type=['nowords'])
        return tuple(map(self.transform_bug, json['bugs']))

def main():
    parser = argparse.ArgumentParser('crawler')
    parser.add_argument('template', metavar='TEMPLATE', type=Path,
                        help='Template to render')
    parser.add_argument('-o', '--output', metavar='PATH',
                        type=argparse.FileType('w', encoding='utf-8'),
                        help='output file')
    args = parser.parse_args()

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(args.template.parent),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    args.output.write(env.get_template(args.template.name).render(
        b=Bugzilla(),
        now=datetime.utcnow(),
    ))

if __name__ == '__main__':
    logging.basicConfig(format='{asctime} | [{levelname}] {message}', style='{',
                        level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S")
    main()
