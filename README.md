What's GoodMake?
==============

GoodMake is a simpler and more flexible build system.  It lets you use a
scripting language of your choice to define recipes and dependencies, and then
intelligently runs just the right recipes, in parallel, to build the result
you want.  You do *not* have to know ahead of time what the dependencies will
be.  This greatly simplifies writing build recipes -- you just specify target
patterns and don't have to learn a special-purpose build system language.

GoodMake's design borrows heavily from the grand-daddy of make systems, [Gnu
Make](https://www.gnu.org/software/make/), and from the wonderful
[Redo](https://cr.yp.to/redo.html) system.

Compared to Gnu Make
====================

GoodMake is designed to allow much more powerful descriptions of the
dependencies between recipes, while being simple to read, write, and debug,
resulting in more reliable build systems.  GoodMake:

* Lets you use any scripting language for your recipes
* Doesn't require you to learn a make file "language"
* Lets you write arbitrary code to determine dependencies
* Lets you organize your recipes into separate make files
* Plays well with recursive make files
* Uses file checksums to determine if dependencies have changed
* You can run your make files from any directory

Compared to Redo
================

GoodMake:

* Lets you use any scripting language for your recipes
* Lets you consolidate multiple recipes into a single file
* Lets you specify multiple target patterns that use the same recipe
* Does not require your make files to be in any particular place

Usage
=====

Here's a moderately sophisticated and heavily-commented shell-script executable "make.sh" file, which contains 5 recipes:

    #! /usr/local/bin/goodmake /bin/sh -sex
    
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

To sort all the files, you'd simply type:

    ./make.sh

This will sort all the files in the directory `src`, and put the sorted results in `tgt`.  The `$0` variable is the make script `./make.sh`, and the `$1` variable is the target currently being built.  The build works as follows:

1. The `./make.sh` script with no arguments runs the recipe for `default`
2. The `default` recipe requires `all`, which requires `tgt.ls`, which lists the files in `src` into a file called `tgt.ls`.  If new files are added to `src`, the `tgt.ls` will change, causing the `all` recipe to re-run.
3. Next, the `all` recipe requires corresponding `tgt/filename` dependencies for each `src/filename` from the `tgt.ls`.  If any of these `src` files have changed, the corresponding `tgt/*` pattern recipe will be re-run.
4. A `tgt/filename` requirement uses the `tgt/*` recipe to create the target by running `sort` on the corresponding `src` file.

If you want to create or update just one sorted file, you could type:

    ./make.sh tgt/filename

Goodmake Script File Syntax
===========================

A GoodMake script file is a file in a scripting language of your choice, along with strategically placed comments that break the file up into "recipes" to be run depending on the build target.  You'll typically want to make the GoodMake file executable.

The familiar first comment line is the OS "shebang" that says this should be executed with
GoodMake.  The line points to goodmake, and specifies an interpreter command.  Here is a Python shebang:

    #! /usr/local/bin/goodmake /usr/bin/python3 -

and a Bash shebang:

    #! /usr/local/bin/goodmake /bin/sh -se

Subsequent blank and comment lines are ignored. "Stanzas" of code are introduced with a "sheque" comment that specifies (shell glob) targets that the stanza will apply to.  For example a Python or Bash script might include the target line:

    #? tgt/sorted.txt

And a node script might include the target line:

    //? tgt/sorted.txt

A "shebang" anywhere other that the first line, is like a "sheque" but indicates the recipe should always be run, regardless of any dependencies:

    #! tgt/sorted.txt

After a shebang, lines are interpreted.  A recipe for a target is built out of *all* of the matching stanzas.  In the recipe, the positional arguments are set:

0.  The script path (depending on the interpreter)
1.  The target
2.  The script path (regardless of interpreter)

Here's a full python `make.py` script file example:

    #! /usr/local/bin/goodmake /usr/bin/python3 -
        
    #? tgt/*
        import subprocess
        import sys
    
    #? tgt/sorted.txt
        inputFile = 'src/input.txt'
        subprocess.run([sys.argv[2], inputFile])
    
        with open(inputFile) as input:
            lines = input.readlines()
            lines.sort()
            with open(sys.argv[1], 'w') as output:
                output.writelines(lines)
    
    #! !sayhi
        print("Hello, World")

When Recipes Are Run
====================

When an recipe is run, it may update the target, it creates a checksum, and it logs a build.  A recipe is run when one of its target patterns is requested, and:

- The recipe starts with shebang (#!), or
- There's no successful build log, or 
- The checksum has changed, or
- The recipe has changed, or
- if any known dependencies have changed

When Targets Are Considered Changed
===================================

A checksum is taken on dependency targets that are existing files.  Targets that are missing, or are directories, or whose patterns started with "!", don't have checksums.  A target is considered changed if:

- The target checksum exists and has changed, or
- There is no checksum, and the recipe has been re-run

It's a "missing recipe" error if there's no recipe and no checksum and the target doesn't already exist.

Parallel Builds
===============

If a script is called with multiple dependencies, then these dependencies are checked (and rebuilt if necessary) in parallel, in batches of up to 8 at a time.  The parallelism can be specified with the GM_THREADS environment variable.

What To Clean
=============

You may want to clean out all GoodMake files.  After such a clean, no files will have build logs, so all encountered recipes will be run when updating.  This is pretty safe.

    find -name '*.gm' -delete

You may want to delete all the built files.  When a recipe is run, it creates a build log file.  You could delete all files that have an accompanying `.gm` file.  This is less safe, if you have any recipes that don't actually know how to create their targets.  GoodMake includes a Linux script `goodmake_clean.sh` to list or to clean all built files.

Environment Variables
=====================

GoodMake uses the following environment variables:

- `LOG` - Set logging level to ERROR, WARN (default), INFO, or DEBUG.
- `GM__REMAKE` - Set to TRUE to cause all targets to be re-made.
- `GM__TIMEOUT` - Number of seconds to wait for concurrency locks.
- `GM_THREADS` - Set the maximum number of threads for parallel builds.
- `GM__FILE` - Internal variable for communicating between GoodMake processes.
- `GM__STARTTIME` - Internal variable for communicating between GoodMake processes.

Examples
========

Specifying an *external* file dependency
----------------------------------------

This triggers a rebuild if someone or something changes `external_file`:

    #? my_target
        $0 external_file

The first successful build will create a build log for `my_target` with checksums for both `external_file` and `my_target`.  If the `external_file` changes, then it will trigger a re-run of `my_target` recipe.

How to identify a *missing* dependency recipe
---------------------------------------------

If `nosuchdep` doesn't exist, an error will be thrown and the build will stop.

    #? my_target
        $0 nosuchdep

Sometimes you may have an erroneous set of recipes that list a non-existent dependency with no recipe to build it.  If nosuchdep does not exist, or is a directory, look in the logs for a message that says "missing recipe".

Ensuring a recipe is *always* run
---------------------------------

This is useful if some dependencies are not identifiable ahead of time.  We still want to use a checksum to see if anything has changed.

    #! my_target
        ls >$1

If the pattern line starts with shebang instead of sheque, the recipe is always run.  `my_target` will only be considered changed (causing parent recipes to be re-run) if its checksum changes.

Combining multiple *dependencies* into a single target
------------------------------------------------------

This defines one target dependency as the equivalent of several other dependencies:

    #? !my_prereqs
        $0 dep1 dep2 dep3

Since `!my_prereqs` starts with a "!", any checksum is ignored, and so `my_prereqs` will be considered changed every time the recipe is run, which will be every time the dependencies are changed.

Naming a simple *script* to run from the command line
-----------------------------------------------------

    #! doit
        ls -lht

This recipe will always run, because it starts with a shebang.

Refreshing after a certain amount of time
-----------------------------------------

Here are some examples of how you can trigger rebuilds from things other than file changes:

    #! .every-day
        touch -d yesterday .yesterday
        [ $1 -nt .yesterday ] || date>$1
    
    #! .each-boot
        touch -d $(uptime -s) .reboot
        [ $1 -nt .reboot ] || date>$1
    
    #! .each-install
        # This should work on debian systems
        FILE=$(ls -1t /var/log/installer | tail -1)
        [ $1 -nt "$FILE" ] || date>$1
    
    #! .each-upgrade
        [ $1 -nt /etc/lsb-release ] || date>$1

A Linux script for some of the above periodic builds is included in `goodmake_every.sh`.

Dynamic lists of dependencies
-----------------------------

With Gnu Make, it's pretty tricky to process all files in a directory, when you don't know the exact list of files ahead of time.  Here's one way you can do it with GoodMake:

    #! tgt.ls
        ls $SRC_DIR | while read file; do
            echo tgt/$file
        done > $1

This creates a `tgt.ls` list of the files to be built.  

Other Linux shell techniques are to use `xargs` to feed dependencies to `$0`, and to use things like `${1%.obj}` to get source file names from target names.

Other tips
----------

A useful set of Linux shell variables and functions is included in `goodmake_lib.sh`.

GoodMake creates a `.target.gm` file for each successful build of `target`.  It lists dependencies and build results in a tab-delimited format.

Contributing
============

Feedback and contributions are welcome.  GoodMake is on [GitHub](https://github.com/AmesCornish/GoodMake) and [PyPI](https://pypi.org/project/goodmake/).

License
=======

GoodMake is distributed under the terms of the GNU General Public License v3.0.
