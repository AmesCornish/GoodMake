#! ../goodmake.py /bin/sh -sex

# Default action is to sort all files in src directory
#   "!default" indicates that "default" is a dummy target.  Don't checksum it.
#? !default
    $0 all

# The "*" matches all targets, so this variable is always set
#? *
    SRC_DIR=src

# Make a target file by sorting a source file
#? tgt/*
    # $0 - This goodmake script
    # $1 - The target, which matches one of the #? patterns for this recipe

    # Get the name of the corresponding source file
    SRC=$SRC_DIR/$(basename $1)

    # Flag the source file as a dependency
    $0 $SRC

    # Sort the source into the target
    sort $SRC > $1

# Sort all files in src directory
#? !all
    # The tgt list itself is a dependency
    $0 tgt.ls
    # Make all the listed target files
    $0 $(cat tgt.ls)

# Make a list of all target files, based on source files
#   "#!" means to always run this recipe, in case files in $SRC_DIR changed
#! tgt.ls
    ls $SRC_DIR | while read file; do
        echo tgt/$file
    done > $1
