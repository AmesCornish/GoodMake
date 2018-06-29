#! /usr/local/bin/goodmake /bin/sh -se

#! retest
    rm -rf test/results .test.gm
    $0 test

#? !test
    cd test
    DIR=results
    ./suite.sh
    git status --short ${DIR}
    git diff --quiet ${DIR}
    [ -z "$(git ls-files --other --directory --exclude-standard $DIR)" ]
    echo "TESTS PASSED"

#! clean
    rm -rf test/results dist goodmake.egg-info
    rm -f $(scripts/goodmake_clean.sh)

#! pypi
    ./setup.py sdist bdist_wheel upload
    # ./setup.py sdist bdist_wheel upload -r pypitest
    ./setup.py clean --all
    rm -rf *.egg-info
