#! /usr/bin/python3

# Copyright (c) 2017-2018 by Ames Cornish
# Licensed "as is", with NO WARRANTIES, under the GNU General Public License v3.0

""" GoodMake for simple recursive build scripts. """

# from __future__ import annotations  # For Python 3.7+

from concurrent.futures import ThreadPoolExecutor as ThreadPool
from contextlib import contextmanager
from datetime import datetime, timedelta
from enum import Enum
from functools import partial
from random import random
from typing import Any, cast, Dict, Generator, Iterable, List, Match, Optional, Tuple
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

theVersion = '0.2.0'

theDepName = 'GM_FILE'
theLogName = 'LOG'
theRemakeName = 'GM_REMAKE'
theTimeoutName = 'GM_TIMEOUT'
theTimestampName = 'GM_STARTTIME'
theThreadsName = 'GM_THREADS'

################ TYPES ####################

try:
    FullPath = path.FullPath
except Exception:
    FullPath = None  # type: ignore  # Only for runtime

Hash = str
Seconds = float
ShellCommand = List[str]

###########################################

# Rough maximum wait for goodmake file locks, in seconds
theLockWait: Seconds = int(os.environ.get(theTimeoutName, 60))

# Number of retries during wait
theLockTries = 10

theDateFormat = '%Y-%m-%dT%H:%M:%S.%f'
theDebugLogFormat = '%(filename)s[%(lineno)d]: %(message)s'
theLogFormat = '%(message)s'

theStampAccuracy = timedelta(0, 0, 10000)

theMaxThreads = int(os.environ.get(theThreadsName, 8))

###########################################

def date2str(timestamp: datetime = None) -> str:
    if timestamp is None:
        return 'None'
    return datetime.strftime(timestamp, theDateFormat)


def str2date(timestamp: str) -> datetime:
    if timestamp == 'now':
        return datetime.now()
    return datetime.strptime(timestamp, theDateFormat)


def str2path(text: str, dirPath: FullPath) -> FullPath:
    return path.normpath(path.join(dirPath, text))


def path2str(fullPath: FullPath, dirPath: FullPath) -> str:
    """ Makes a pretty relative string. """
    relPath = path.relpath(fullPath, dirPath)
    if len(relPath) > len(fullPath):
        relPath = fullPath
    return relPath


def hashString(str: str) -> Hash:
    return hashBuffers([str.encode('utf-8')])


def hashBuffers(buffers: Iterable[bytes]) -> Hash:
    d = hashlib.md5()
    for buf in buffers:
        d.update(buf)
    return d.hexdigest()


###########################################

class BuildError(Exception):
    def __init__(self, message: str, returncode: int = 1):
        super(BuildError, self).__init__(message)
        self.returncode = returncode


class BuildCommand:
    def __init__(self, dirPath: FullPath, scriptPath: str, targetPath: str):
        self.dirPath = dirPath
        self.script = scriptPath
        self.target = targetPath

    @property
    def scriptPath(self) -> FullPath:
        return str2path(self.script, self.dirPath)

    @property
    def targetPath(self) -> FullPath:
        return str2path(self.target, self.dirPath)


class Recipe:
    def __init__(self, interpreter: ShellCommand, script: Optional[str], always: bool, ignore: bool):
        self.interpreter = interpreter
        self.script = script
        self.always = always
        self.ignore = ignore

    def run(recipe, command: BuildCommand, vars: dict) -> None:
        if recipe.script is None:
            raise BuildError("No recipe for " + command.target)

        env = os.environ.copy()
        env.update(vars)

        description = '%s %s (with %s)' % (
            command.script, command.target, ' '.join(recipe.interpreter)
        )

        logger.debug('Running %s', description)

        process = subprocess.Popen(
            [command.script] + recipe.interpreter[1:] + [command.target, command.script],
            executable=recipe.interpreter[0],
            stdin=subprocess.PIPE,
            env=env,
            cwd=command.dirPath,
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


class BuildEvent(BuildCommand):

    @staticmethod
    def fromString(line: str, dirPath: FullPath) -> 'BuildEvent':
        args = line.rstrip().split('\t')
        return BuildEvent(BuildCommand(str2path(args[0], dirPath), *args[1:3]), *args[3:])

    @staticmethod
    def fromRecipe(command: BuildCommand, recipe: Recipe) -> 'BuildEvent':
        stanza = BuildEvent._hashStanza(recipe)
        return BuildEvent(command, stanza)

    nonsums = ['directory', 'ignore']
    header = ['directory', 'script', 'target', 'recipe', 'timestamp', 'result']

    def __init__(
        self,
        command: BuildCommand,
        stanza: Hash,
        timestamp: str = None,
        checksum: Hash = None
    ):
        super(BuildEvent, self).__init__(command.dirPath, command.script, command.target)
        self.stanza = stanza
        self.timestamp = timestamp
        self.checksum = checksum

    def refresh(self, timestamp: datetime = None, ignoreChecksum: bool = False) -> None:
        self.timestamp = date2str(timestamp)
        self.checksum = (
            'ignore' if ignoreChecksum
            else self._hashFile(self.targetPath)
        )

    def toString(self, dirPath: FullPath) -> str:
        return '\t'.join([
            path2str(self.dirPath, dirPath),
            self.script,
            self.target,
            self.stanza,
            self.timestamp or '',
            self.checksum or '',
        ])

    @staticmethod
    def _hashStanza(recipe: Recipe) -> Hash:
        if recipe.script is None:
            return 'missing'
        elif not recipe.script:
            return 'empty'

        return hashString(recipe.script)

    @staticmethod
    def _hashFile(target: FullPath) -> Hash:
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

    def __init__(self, current: BuildEvent, fakeTarget: bool = False):
        self.current = current

        basename = '.' + path.basename(current.target)
        if fakeTarget:
            # This lets two different scripts use the same fake target (e.g. !default)
            basename += '_' + hashString(current.scriptPath)
        basename += '.gm'

        self.targetDir = path.dirname(current.targetPath)
        self.filename: FullPath = str2path(basename, self.targetDir)

        self._lockname = cast(FullPath, self.filename + '.lock')

        self.timestamp: Optional[datetime] = None
        self.last: Optional[BuildEvent] = None
        self.deps: List[BuildEvent] = []

    @contextmanager
    def build(self) -> Generator:
        """ Context manager for dependency building. """
        # Dependency builds will write into self.filename
        with open(self.filename, 'w') as file:
            file.write('\t'.join(BuildEvent.header) + '\n')
            logger.debug('Created %s', self.filename)

        yield

        # write final header to target
        logger.debug('Writing %s to %s', self.current.target, self.filename)
        with open(self.filename, 'a') as file:
            file.write(self.current.toString(self.targetDir) + '\n')

    def checked(self) -> None:
        os.utime(self.filename)

    def _parse(self) -> None:
        if not path.exists(self.filename):
            return

        with open(self.filename, 'r') as info:
            next(info)  # Header
            for line in info:
                self.deps.append(BuildEvent.fromString(line, self.targetDir))
        self.last = self.deps[-1] if len(self.deps) > 0 else None
        self.deps = self.deps[:-1]
        self.timestamp = datetime.fromtimestamp(path.getmtime(self.filename))
        logger.debug('Read %s: %s', self.filename, self.timestamp)

        if self.last and self.last.scriptPath != self.current.scriptPath:
            raise BuildError(
                '%s is trying to re-use %s created by %s.  Deleting.' %
                (self.current.scriptPath, self.filename, self.last.scriptPath)
            )

    def __enter__(self) -> 'Info':
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

    def __exit__(self, *exc: Any) -> bool:
        if path.exists(self.filename):
            if exc[0] is not None:
                os.remove(self.filename)
            else:
                os.utime(self.filename)
                logger.debug(
                    'Write %s: %s',
                    self.filename, datetime.fromtimestamp(path.getmtime(self.filename))
                )
        logger.debug('Unlocking %s', self._lockname)
        os.remove(self._lockname)
        return False


class Script:

    """ Parsed build file with script stanzas by target pattern. """

    def __init__(self, path: FullPath):
        self._stanzas: List[Tuple[str, bool, str]] = []
        self._parse(path)

    def match(self, target: str) -> Recipe:
        result: Optional[str] = None
        always, ignore, generic = False, False, True
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

    def _addStanza(self, pattern: Optional[str], always: bool, stanza: str) -> None:
        if pattern is None:
            return

        self._stanzas.append((pattern, always, stanza))

    _shebang = re.compile('(#|//|;|--)(\?|!)(.*)$')

    def _parse(self, path: FullPath) -> None:
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
                        indent = cast(Match[str], re.match('\s*', line)).group(0)

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


class Builder:
    error: Optional[Exception] = None

    @staticmethod
    def sleep(amount: Seconds) -> None:
        if Builder.error is None and amount > 0:
            time.sleep(amount)
        if Builder.error:
            logger.debug('%s: Another thread errored %s', os.getpid(), Builder.error)
            raise Builder.error

    def __init__(self) -> None:
        self.timestamp = str2date(os.environ.get(theTimestampName, 'now'))
        logger.debug('Build: %s', self.timestamp)

        self._remake = os.environ.get(theRemakeName, 'false').lower() in ['true', 'yes', '1', 'on']

        self._scripts: Dict[FullPath, Script] = {}
        self._scriptLock = threading.Lock()

    def build(self, command: BuildCommand) -> BuildEvent:
        """ Build <target> with <script> from current directory if it needs updating.

        Returns BuildEvent for target.
        """
        recipe = self._getRecipe(command)
        current = BuildEvent.fromRecipe(command, recipe)

        logger.debug('Checking %s', current)

        if current.stanza == 'missing' and path.exists(command.targetPath):
            logger.info('Dependency %s', command.target)
            current.refresh(None, False)
            return current

        current.timestamp = date2str(self.timestamp)

        with Info(current, recipe.ignore) as info:
            isOK, reason = self._check(info, recipe)

            def log(level: int, action: str) -> None:
                logger.log(level, '%s %s from %s because %s', action, command.target, current.script, reason)

            if isOK and info.last:
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
                recipe.run(command, envVars)
                info.current.refresh(self.timestamp, recipe.ignore)

            return info.current

    def _check(self, info: Info, recipe: Recipe) -> Tuple[bool, str]:
        if info.last is None:
            return False, 'it hasn\'t completed'

        # This ensures any given recipe is only run once per build
        # It will not check for side-effects
        logger.debug('last build: %s this build: %s', info.timestamp, self.timestamp)
        if info.timestamp and self.timestamp - info.timestamp <= theStampAccuracy:
            return True, 'it was checked this build'

        if recipe.always:
            return False, 'it\'s a shebang recipe'

        if (
            info.current.stanza != info.last.stanza or
            info.current.dirPath != info.last.dirPath
        ):
            return False, 'its recipe changed'

        # This checks for changes from outside goodmake
        if not recipe.ignore:
            info.current.refresh(None, False)
            if info.current.checksum and info.current.checksum != info.last.checksum:
                return False, 'it changed to ' + info.current.checksum

        for dep in info.deps:
            try:
                updatedDep = self.build(dep)
            except BuildError as e:
                return False, dep.target + ' raised error "' + str(e) + '"'

            if updatedDep.checksum and updatedDep.checksum != dep.checksum:
                return False, dep.target + ' changed to ' + updatedDep.checksum

            if updatedDep.checksum in BuildEvent.nonsums:
                if updatedDep.timestamp and updatedDep.timestamp != dep.timestamp:
                    return False, dep.target + ' was updated ' + updatedDep.timestamp

        if self._remake:
            return False, theRemakeName + ' environment variable is set'

        info.checked()
        return True, 'dependencies unchanged'

    def _getRecipe(self, command: BuildCommand) -> Recipe:
        # Get an absolute, canonical path
        scriptPath = path.realpath(command.scriptPath)

        with self._scriptLock:
            if scriptPath not in self._scripts:
                self._scripts[scriptPath] = Script(scriptPath)

        scripts = self._scripts[scriptPath]

        return scripts.match(command.target)


def main(argv: List[str] = sys.argv) -> int:
    level = os.environ.get(theLogName, 'WARN').upper()
    logging.basicConfig(
        level=level,
        format=theDebugLogFormat if level == 'DEBUG' else theLogFormat
    )
    logger.info('GoodMake version %s', theVersion)

    # interpreter = argv[1]  # interpreter will be taken from the file shebang
    scriptPath = argv[2]
    targetPaths = argv[3:] or ['default']
    depPath = cast(Optional[FullPath], os.environ.get(theDepName, None))
    currentDir = os.getcwd()

    logger.debug('PID %s:%s for %s', os.getpid(), os.getppid(), targetPaths)

    builder = Builder()

    def runBuild(target: str) -> None:
        if Builder.error:
            return
        try:
            command = BuildCommand(currentDir, scriptPath, target)
            event = builder.build(command)

            if depPath:
                logger.debug('Writing %s to parent %s', target, depPath)
                with open(depPath, 'a') as file:
                    file.write(event.toString(path.dirname(depPath)) + '\n')
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
        return int(getattr(Builder.error, 'returncode', 1))

    return 0


if __name__ == "__main__":
    sys.exit(main())
