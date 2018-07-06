#! ../goodmake.py /bin/sh -sex


# Default action is to sort all files in src directory
#? default
    $0 all

# Make a target file by sorting a source file
#? tgt/*
    # $0 - This goodmake script
    # $1 - The target, which matches one of the #? patterns

    # Get the name of the corresponding source file
    SRC=src/$(basename $1)

    # Flag the source file as a dependency
    $0 $SRC

    # Sort the source into the target
    sort $SRC > $1


# Sort all files in src directory
#   "all" is a dummy pattern.  Don't checksum it.
#? !all
    # The tgt list is a dependency
    $0 src/list
    # Make all the target files
    $0 $(cat src/list)


# Make a list of all target files, based on source files
#   Always run this recipe, in case files in src changed
#! src/list
    ls src | while read file; do
        echo tgt/$file
    done > $1
