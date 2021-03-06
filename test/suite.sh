#! ../goodmake.py /bin/sh -se

#? !default
    $0 results/example
    $0 results/simple
    $0 results/python
    $0 results/dotfile
    $0 results/parallel
    $0 results/errors
    $0 results/missing
    $0 results/every
    $0 results/fake
    $0 results/conflict

##############################################

#? results/*
    $0 ../goodmake.py

    unset GM_STARTTIME
    unset GM_FILE
    export LOG=INFO
    export GM_THREADS=1
    DIR=$(dirname $0)
    # DIR=$(readlink --canonicalize $(dirname $0))

    CLEAN=$(ls .*.gm | grep -v '^.default' || true)
    rm -rf src $CLEAN tgt.ls
    rm -f  /dev/shm/reboot-timestamp  /dev/shm/.reboot-timestamp.gm
    cp -a dist src

    # Redirect all output to build target
    exec >$1 2>&1
    set -x

##############################################

#? results/example
    $DIR/example.sh all

#? results/simple
    $DIR/make.sh tgt/sorted.txt
    $DIR/make.sh tgt/sorted.txt
    echo "alfred" >> src/input.txt
    $DIR/make.sh tgt/sorted.txt

#? results/python
    $DIR/make.py tgt/sorted.txt

#? results/dotfile
    $DIR/make.sh tgt/usedot
    $DIR/make.sh tgt/usedot

#? results/parallel
    set +x
    export GM_THREADS=8
    for N in $(seq 30); do
        echo "tgt/sorted.txt tgt/.dotfile"
    done | { set -x; xargs $DIR/make.sh; }

#? results/circular
    $DIR/make.sh circular-a

#! !results/ctlc
    # This gives you an opportunity to hit ctl-c and see what happens
    # Not for batch scripts yet
    $DIR/make.sh sleep sleep sleep

#? results/errors
    export GM_THREADS=8
    $DIR/make.sh sleep sleep sleep error || echo "Error#" $?

#? results/missing
    $DIR/make.sh no_recipe || echo "Error #" $?

#? results/parallel results/errors
    # We can't depend on the sequence
    sort $1 > $1.tmp
    mv $1.tmp $1

#? results/every
    every=../scripts/goodmake_every.sh
    $0 $every
    $every .hour
    $every .boot
    $every .os_install

#? results/fake
    # Two different scripts should both be able to make !fake
    $DIR/make.sh tgt/fake
    $0 tgt/fake

#? !tgt/fake
    echo $0>$1

#? results/conflict
    # Two different scripts both creating 'conflict' should produce error
    $DIR/make.sh tgt/conflict
    $0 tgt/conflict || echo "Error#" $?

#? tgt/conflict
    echo $0>$1

##############################################

#? results/*
    set +x
    sync $1
    sed -i --file results.sed $1
    rm -rf tgt src

##############################################
##############################################
