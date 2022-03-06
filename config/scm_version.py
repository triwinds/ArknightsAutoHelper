"""
get version from git working tree
"""
import os
import subprocess

try:
    _dir = os.path.dirname(__file__)
    branch = subprocess.check_output(('git', 'rev-parse', '--abbrev-ref', 'HEAD'), cwd=_dir).strip()
    _description = subprocess.check_output(['git', 'describe', '--tags', '--always', '--dirty'], cwd=_dir).strip()

    # version = (b'%b+%b' % (branch, _description)).decode()
    version = (b'%b' % branch).decode()
except:
    version = 'UNKNOWN'
