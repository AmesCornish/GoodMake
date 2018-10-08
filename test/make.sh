#! ../goodmake.py /bin/sh -se

#? !default
    echo "Default no-op"

#? tgt/sorted.txt
    $0 src/input.txt
    sort src/input.txt > "$1"

#! tgt/.dotfile
    echo "hola" >$1

#? tgt/usedot
    $0 tgt/.dotfile

#? !error
    echo "ERROR" 1>&2
    return 2

#! !sleep
    sleep 30

#? circular-a
    $0 erehwon circular-b
    false

#? circular-b
    $0 circular-a

#? tgt/conflict
    echo $0>$1

#? !tgt/fake
    echo $0>$1
