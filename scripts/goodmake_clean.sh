#! /bin/sh -e

# Clean up goodmake files.

while getopts f OPT; do
case $OPT in
    f) FORCE=y;;
esac done
shift "$((OPTIND-1))"

# File list should be reviewed before deleting
if [ -n "$FORCE" ]; then
    RM() { echo $@; rm $@; }
else
    # just list deletable files
    RM() { echo $@; }
fi

# Don't delete anything newer than the current build start
CURRENT=$(mktemp)
[ -z "$GM_STARTTIME" ] || touch -d "$GM_STARTTIME" "$CURRENT"

find "$@" -name '.*.gm.lock' | while read GM; do
    [ "$CURRENT" -nt "$GM" ] || continue
    RM "$GM"
done

find "$@" -name '.*.gm' | while read GM; do
    [ "$CURRENT" -nt "$GM" ] || continue

    DIR=$(dirname $GM)
    FILE=$(basename $GM)
    FILE=${FILE%.gm}
    FILE=${FILE#.}
    TARGET="$DIR/$FILE"

    BUILD_DATE=$(tail -n1 "$GM" | cut -f5)
    BUILD_DATE=$(date +%s --date "$BUILD_DATE")
    BUILD_SUM=$(tail -n1 "$GM" | cut -f6)

    GM_DATE=$(stat --format=%Y "$GM")

    if ! [ -f "$TARGET" ]; then
        RM "$GM"
        continue
    fi

    TGT_DATE=$(stat --format=%Y "$TARGET")
    TGT_SUM=$(md5sum "$TARGET" | cut -d' ' -f1)

    # Check to make sure we're deleting a file created by GoodMake:

    # target mod date should be after goodmake timestamp
    #   (last line of goodmake file)
    # target mod date should be before goodmake file mod date
    # target md5 checksum should match goodmake file checksum

    if [ "$TGT_DATE" -lt "$BUILD_DATE" ]; then
        echo "$TARGET pre-dates GoodMake build" >&2
    elif [ "$TGT_DATE" -gt "$GM_DATE" ]; then
        echo "$TARGET modified after GoodMake check" >&2
    elif [ "$TGT_SUM" != "$BUILD_SUM" ]; then
        echo "$TARGET doesn't match GoodMake build" >&2
    else
        RM "$GM"
        RM "$TARGET"
    fi
done

rm "$CURRENT"
