# Bash Completion script for GoodMake

_goodmake_targets()
{
    cmd="$1"
    word="$2"

    # TODO: Check that it's really a GoodMake script

    # local cur prev opts
    COMPREPLY=()
    # cur="${COMP_WORDS[COMP_CWORD]}"
    # prev="${COMP_WORDS[COMP_CWORD-1]}"

    pats=$(tail +2 $cmd | grep -E '^#(!|\?)' | cut -c3-)

    tgts=
    for pat in $pats; do
        tgts="$tgts ${pat#\!}"
    done

    COMPREPLY=( $(compgen -W "${tgts}" -- ${word}) )

    # if [[ ${cur} == -* ]] ; then
    #     COMPREPLY=( $(compgen -W "${opts}" -- ${cur}) )
    #     return 0
    # fi
}

complete -F _goodmake_targets ./make.sh ./install.sh
