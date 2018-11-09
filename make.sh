#! goodmake.py /bin/sh -se

#? !default
    $0 test lint version.txt

#! !retest
    rm -rf test/results .test.gm
    $0 test

#? !test
    cd test
    DIR=results
    ./suite.sh
    git status --short -- ${DIR}
    git diff --quiet -- ${DIR}
    [ -z "$(git ls-files --other --directory --exclude-standard $DIR)" ]
    echo "TESTS PASSED"

#? !lint
    MYPYPATH=./stubs mypy goodmake.py

#! !clean
    rm -rf test/results dist goodmake.egg-info
    rm -f $(scripts/goodmake_clean.sh)

#! !test-pypi
    opts="-r pypitest"

#! !pypi
    opts=

#! pypi test-pypi
    $0 README.rst version.txt
    ./setup.py sdist bdist_wheel upload $opts
    ./setup.py clean --all
    rm -rf *.egg-info

#? README.rst
    pandoc --from markdown --to rst $readme >$1

#? version.txt
    $0 goodmake.py
    python3 -c "import goodmake; print(goodmake.theVersion)" >$1

#! test-install
    sudo -H python3 -m pip install --upgrade --no-cache-dir --index-url https://test.pypi.org/simple/ goodmake

#! dev-install
    $0 README.rst version.txt
    ./setup.py bdist_wheel
    sudo ./setup.py install
    ./setup.py clean --all
    rm -rf *.egg-info

#? .completion
    src=scripts/bash_completion.sh
    tgt=/etc/bash_completion.d/goodmake
    $0 $src
    sudo cp $src $tgt
    ln -sf $tgt $1
