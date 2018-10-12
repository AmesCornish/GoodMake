#! /usr/bin/python3

# Copyright (c) 2017-2018 by Ames Cornish
# Licensed "as is", with NO WARRANTIES, under the GNU General Public License v3.0

""" REdo-and-MORe script for simple recursive build scripts. """

from contextlib import contextmanager
from functools import partial
from concurrent.futures import ThreadPoolExecutor as ThreadPool
from random import random
import datetime
import fnmatch
import hashlib
import logging
import os
import os.path as path
import re
import subprocess
import sys
import threading
import time

logger = logging.getLogger()

theVersion = '0.1.4'

theDepName = 'GM_FILE'
theLogName = 'LOG'
theRemakeName = 'GM_REMAKE'
theTimeoutName = 'GM_TIMEOUT'
theTimestampName = 'GM_STARTTIME'
theThreadsName = 'GM_THREADS'

# Rough maximum wait for goodmake file locks, in seconds
theLockWait = int(os.environ.get(theTimeoutName, 60))
# Number of retries during wait
theLockTries = 10

theDateFormat = '%Y-%m-%dT%H:%M:%S.%f'
theDebugLogFormat = '%(filename)s[%(lineno)d]: %(message)s'
theLogFormat = '%(message)s'

theStampAccuracy = datetime.timedelta(0, 0, 10000)

theMaxThreads = int(os.environ.get(theThreadsName, 8))

def date2str(timestamp):
    if timestamp is None:
        return 'None'
    return datetime.datetime.strftime(timestamp, theDateFormat)


def str2date(timestamp):
    if timestamp == 'now':
        return datetime.datetime.now()
    return datetime.datetime.strptime(timestamp, theDateFormat)


def hashString(str):
    return hashBuffers([str.encode('utf-8')])


def hashBuffers(buffers):
    d = hashlib.md5()
    for buf in buffers:
        d.update(buf)
    return d.hexdigest()


@contextmanager
def chdir(directory):
    old = os.getcwd()
    os.chdir(directory)
    yield
    os.chdir(old)


class BuildError(Exception):
    def __init__(self, message, returncode=1):
        super(BuildError, self).__init__(message)
        self.returncode = returncode


class BuildEvent:

    @staticmethod
    def fromString(line):
        return BuildEvent(*line.rstrip().split('\t'))

    @staticmethod
    def fromRecipe(script, target, recipe):
        stanza = BuildEvent._hashStanza(recipe)
        return BuildEvent(os.getcwd(), script, target, stanza)

    nonsums = ['directory', 'ignore']
    header = ['directory', 'script', 'target', 'recipe', 'timestamp', 'result']

    def __init__(self, cwd, script, target, stanza, timestamp=None, checksum=None):
        self.dir = cwd
        self.script = script
        self.target = target
        self.stanza = stanza
        self.timestamp = timestamp
        self.checksum = checksum

    def refresh(self, timestamp=None, ignoreChecksum=False):
        self.timestamp = date2str(timestamp)
        self.checksum = 'ignore' if ignoreChecksum else self._hashFile(self.target)

    def __str__(self):
        return '\t'.join([
            self.dir,
            self.script,
            self.target,
            self.stanza,
            self.timestamp or '',
            self.checksum or '',
        ])

    def fullScriptPath(self):
        return path.normpath(path.join(self.dir, self.script))

    @staticmethod
    def _hashStanza(recipe):
        if recipe.script is None:
            return 'missing'
        elif not recipe.script:
            return 'empty'

        return hashString(recipe.script)

    @staticmethod
    def _hashFile(target):
        if not path.exists(target):
            return 'missing'

        if path.isdir(target):
            return 'directory'

        if path.getsize(target) == 0:
            return 'empty'

        with open(target, mode='rb') as f:
            return hashBuffers(iter(partial(f.read, 4096), b''))


class Info:

    """ File with info about last build of target.

    File contains BuildEvent line for each dependency, and
    last line is BuildEvent for the target.

    Also is a context manager to hold lock on info file. """

    def __init__(self, current, fakeTarget=False):
        self.current = current

        # This lets two different scripts use the same fake target (e.g. !default)
        basename = '.' + path.basename(current.target)
        if fakeTarget:
            basename += '_' + hashString(current.fullScriptPath())
        basename += '.gm'

        self.filename = path.join(path.dirname(current.target), basename)

        self._lockname = self.filename + '.lock'

        self.timestamp = None
        self.last = None
        self.deps = []

    @contextmanager
    def build(self):
        """ Context manager for dependency building. """
        # Dependency builds will write into self.filename
        with open(self.filename, 'w') as file:
            file.write('\t'.join(BuildEvent.header) + '\n')
            logger.debug('Created %s', self.filename)

        yield

        # write final header to target
        logger.debug('Writing %s to %s', self.current.target, self.filename)
        with open(self.filename, 'a') as file:
            file.write(str(self.current) + '\n')

    def checked(self):
        os.utime(self.filename)

    def _parse(self):
        if not path.exists(self.filename):
            return

        with open(self.filename, 'r') as info:
            next(info)  # Header
            for line in info:
                self.deps.append(BuildEvent.fromString(line))
        self.last = self.deps[-1] if len(self.deps) > 0 else None
        self.deps = self.deps[:-1]
        self.timestamp = datetime.datetime.fromtimestamp(path.getmtime(self.filename))
        logger.debug('Read %s: %s', self.filename, self.timestamp)

        if self.last and self.last.fullScriptPath() != self.current.fullScriptPath():
            raise BuildError(
                '%s is trying to re-use %s created by %s.  Deleting.' %
                (self.current.fullScriptPath(), self.filename, self.last.fullScriptPath())
            )

    def __enter__(self):
        lockdir = path.dirname(self._lockname)
        if lockdir:
            os.makedirs(lockdir, exist_ok=True)

        retry = theLockTries
        while True:
            try:
                with open(self._lockname, 'x') as lock:
                    logger.debug('Locking %s', self._lockname)
                    lock.write(str(self.current.timestamp) + '\n')
                break
            except FileExistsError:
                if retry <= 0:
                    raise BuildError(
                        '%s is locked.  Possible circular dependency.' %
                        (self._lockname)
                    )
                retry -= 1

            amount = theLockWait / (2**retry + random())
            logger.log(
                logging.WARN if amount > 2 else logging.DEBUG,
                '%s is locked.  Sleep for %s', self._lockname, amount
            )
            Builder.sleep(amount)

            try:
                with open(self._lockname, 'r') as lock:
                    lockDate = lock.readline().strip()
                    if lockDate and str(self.current.timestamp) != lockDate:
                        logger.debug('current.timestamp: %s', self.current.timestamp)
                        raise BuildError(
                            '%s is locked by %s.  Try deleting it.' %
                            (self._lockname, lockDate)
                        )
            except FileNotFoundError:
                pass  # Lock has been removed

        try:
            self._parse()
        except Exception as e:
            self.__exit__(*sys.exc_info())
            raise BuildError(str(e))

        return self

    def __exit__(self, *exc):
        if path.exists(self.filename):
            if exc[0] is not None:
                os.remove(self.filename)
            else:
                os.utime(self.filename)
                logger.debug(
                    'Write %s: %s',
                    self.filename, datetime.datetime.fromtimestamp(path.getmtime(self.filename))
                )
        logger.debug('Unlocking %s', self._lockname)
        os.remove(self._lockname)
        return False


class Script:

    """ Parsed build file with script stanzas by target pattern. """

    def __init__(self, path):
        self._stanzas = []
        self._parse(path)

    def match(self, target):
        result, always, ignore, generic = None, False, False, True
        for patterns, shebang, stanza in self._stanzas:
            for p in patterns.split():
                bang = p.startswith('!')
                if fnmatch.fnmatch(target, p if not bang else p[1:]):
                    result = result + stanza if result else stanza
                    always = always or shebang
                    ignore = ignore or bang
                    generic = generic and p == '*'
                    break
        return Recipe(self.interpreter, result if not generic else None, always, ignore)

    def _addStanza(self, pattern, always, stanza):
        if pattern is None:
            return

        self._stanzas.append((pattern, always, stanza))

    _shebang = re.compile('(#|//|;|--)(\?|!)(.*)$')

    def _parse(self, path):
        try:
            with open(path) as file:
                bang = Script._shebang.match(next(file))
                if not bang:
                    raise BuildError('Missing first line "#!" in %s' % (path))

                self.interpreter = bang.group(3).split()[1:] or ['/bin/sh', '-se']

                pattern, always, stanza, indent = None, False, '', None

                for line in file:
                    if not line.strip():
                        stanza += line
                        continue

                    if indent is None:
                        indent = re.match('\s*', line).group(0)

                    que = Script._shebang.match(line)

                    if pattern and not que and line.startswith(indent):
                        stanza += line[len(indent):]
                    elif not re.match('\s*(#|//|;|--)', line):
                        raise BuildError('Unexpected line in %s:\n%s' % (path, line))
                    else:
                        self._addStanza(pattern, always, stanza)
                        pattern, always, stanza, indent = None, False, '', None

                    if que:
                        pattern, always = que.group(3), que.group(2) == '!'

                self._addStanza(pattern, always, stanza)
        except FileNotFoundError as e:
            raise BuildError(str(e))


class Recipe:
    def __init__(self, interpreter, script, always, ignore):
        self.interpreter = interpreter
        self.script = script
        self.always = always
        self.ignore = ignore

    def run(recipe, scriptPath, targetPath, vars):
        if recipe.script is None:
            raise BuildError("No recipe for " + targetPath)

        scriptPath = path.realpath(scriptPath)
        relPath = path.relpath(scriptPath)
        if not relPath.startswith('../../'):
            scriptPath = relPath
        if scriptPath == path.basename(scriptPath):
            scriptPath = './' + scriptPath

        env = os.environ.copy()
        env.update(vars)

        description = '%s %s (with %s)' % (
            scriptPath, targetPath, ' '.join(recipe.interpreter)
        )

        logger.debug('Running %s', description)

        process = subprocess.Popen(
            [scriptPath] + recipe.interpreter[1:] + [targetPath, scriptPath],
            executable=recipe.interpreter[0],
            stdin=subprocess.PIPE,
            env=env,
        )

        try:
            process.stdin.write(recipe.script.encode('utf-8'))
            process.stdin.close()
            while process.poll() is None:
                Builder.sleep(.1)
        finally:
            process.kill()
            process.wait()

        if process.returncode != 0:
            logger.debug('Raising %s (%d)', description, process.returncode)
            raise BuildError(
                "%s returned %d" % (description, process.returncode),
                process.returncode,
            )


class Builder:
    error = None

    @staticmethod
    def sleep(amount):
        if Builder.error is None and amount > 0:
            time.sleep(amount)
        if Builder.error:
            logger.debug('%s: Another thread errored %s', os.getpid(), Builder.error)
            raise Builder.error

    def __init__(self):
        self.timestamp = str2date(os.environ.get(theTimestampName, 'now'))
        logger.debug('Build: %s', self.timestamp)

        self._remake = os.environ.get(theRemakeName, 'false').lower() in ['true', 'yes', '1', 'on']

        self._scripts = {}
        self._scriptLock = threading.Lock()

    def build(self, script, target):
        """ Build <target> with <script> from current directory if it needs updating.

        Returns BuildEvent for target.
        """
        recipe = self._getScript(script, target)
        current = BuildEvent.fromRecipe(script, target, recipe)

        logger.debug('Checking %s', current)

        if current.stanza == 'missing' and path.exists(target):
            logger.info('Dependency %s', target)
            current.refresh(None, False)
            return current

        current.timestamp = date2str(self.timestamp)

        with Info(current, recipe.ignore) as info:
            isOK, reason = self._check(info, recipe)

            def log(level, action):
                logger.log(level, '%s %s from %s because %s', action, target, current.script, reason)

            if isOK:
                log(logging.INFO, 'Skip')
                # This uses checksum from last build
                return info.last
            else:
                log(logging.INFO if recipe.always else logging.WARN, 'Make')

            with info.build():
                # This also updates info.current.checksum
                envVars = {
                    theTimestampName: date2str(self.timestamp),
                    theDepName: path.realpath(info.filename),
                }
                recipe.run(script, target, envVars)
                info.current.refresh(self.timestamp, recipe.ignore)

            return info.current

    def _check(self, info, recipe):
        if info.last is None:
            return False, 'it hasn\'t completed'

        # This ensures any given recipe is only run once per build
        # It will not check for side-effects
        logger.debug('last build: %s this build: %s', info.timestamp, self.timestamp)
        if self.timestamp - info.timestamp <= theStampAccuracy:
            return True, 'it was checked this build'

        if recipe.always:
            return False, 'it\'s a shebang recipe'

        if (
            info.current.stanza != info.last.stanza or
            info.current.dir != info.last.dir
        ):
            return False, 'its recipe changed'

        # This checks for changes from outside goodmake
        if not recipe.ignore:
            info.current.refresh(None, False)
            if info.current.checksum != info.last.checksum:
                return False, 'it changed to ' + info.current.checksum

        for dep in info.deps:
            with chdir(dep.dir):
                try:
                    updatedDep = self.build(dep.script, dep.target)
                except BuildError as e:
                    return False, dep.target + ' raised error "' + str(e) + '"'

            if updatedDep.checksum != dep.checksum:
                return False, dep.target + ' changed to ' + updatedDep.checksum

            if updatedDep.checksum in BuildEvent.nonsums:
                if updatedDep.timestamp != dep.timestamp:
                    return False, dep.target + ' was updated ' + updatedDep.timestamp

        if self._remake:
            return False, theRemakeName + ' environment variable is set'

        info.checked()
        return True, 'dependencies unchanged'

    def _getScript(self, script, target):
        # Get an absolute, canonical path
        scriptPath = path.realpath(script)

        with self._scriptLock:
            if scriptPath not in self._scripts:
                self._scripts[scriptPath] = Script(scriptPath)

        scripts = self._scripts[scriptPath]

        return scripts.match(target)


def main(argv=sys.argv):
    level = os.environ.get(theLogName, 'WARN').upper()
    logging.basicConfig(
        level=level,
        format=theDebugLogFormat if level == 'DEBUG' else theLogFormat
    )
    logger.info('GoodMake version %s', theVersion)

    # interpreter = argv[1]  # interpreter will be taken from the file shebang
    scriptPath = argv[2]
    targetPaths = argv[3:] or ['default']
    depPath = os.environ.get(theDepName, None)
    logger.debug('PID %s:%s for %s', os.getpid(), os.getppid(), targetPaths)

    builder = Builder()

    def runBuild(target):
        if Builder.error:
            return
        try:
            event = builder.build(scriptPath, target)

            if depPath:
                logger.debug('Writing %s to parent %s', target, depPath)
                with open(depPath, 'a') as file:
                    file.write(str(event) + '\n')
        except Exception as e:
            logger.debug("Setting %s thread error %s", os.getpid(), e)
            Builder.error = e

    if theMaxThreads <= 1 or len(targetPaths) <= 1:
        for target in targetPaths:
            runBuild(target)
    else:
        with ThreadPool(max_workers=theMaxThreads) as threads:
            threads.map(runBuild, targetPaths)

    if Builder.error:
        logger.error(Builder.error)
        return getattr(Builder.error, 'returncode', 1)


if __name__ == "__main__":
    sys.exit(main())
