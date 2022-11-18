This is a small utility to generate a HTML report of all opened stablreqs and
keywording bugs in Gentoo. This enables us to prioritize the bugs, and notice
bugs we were neglecting.

# Dependencies

- `requests` python library

- `jinja2` python library

# Usage

See `Makefile` for a small example how to run. You just need to call
`generate_report.py` and pass the jinja template.

During the run, it makes 2 requests to bugs (the first one for all current arch
bugs, and the second to check all of their's dependencies). Still, you can
create a `bugs.key` file which contains your API key, so the requests are done
using your account and not anonymous.
