#! /bin/sh -e

# Clean up goodmake files

# RM="rm"
RM="echo"  # just list deletable files

# Don't delete anything newer than the current build
CURRENT=$(mktemp)
[ -z "$GM_STARTTIME" ] || touch -d "$GM_STARTTIME" "$CURRENT"

find -name '.*.gm.lock' | while read REM; do
    [ "$CURRENT" -nt "$REM" ] || continue
    $RM "$REM"
done

find -name '.*.gm' | while read REM; do
    [ "$CURRENT" -nt "$REM" ] || continue

    DIR=$(dirname $REM)
    FILE=$(basename $REM)
    FILE=${FILE%.gm}
    FILE=${FILE#.}
    TARGET="$DIR/$FILE"

    BUILD_DATE=$(tail -n1 "$REM" | cut -f5)
    BUILD_DATE=$(date +%s --date "$BUILD_DATE")
    BUILD_SUM=$(tail -n1 "$REM" | cut -f6)

    REM_DATE=$(stat --format=%Y "$REM")

    # tail -n1 "$REM"

    if ! [ -f "$TARGET" ]; then
        $RM "$REM"
        continue
    fi

    TGT_DATE=$(stat --format=%Y "$TARGET")
    TGT_SUM=$(md5sum "$TARGET" | cut -d' ' -f1)

    # target mod date should be after goodmake timestamp
    #   (last line of goodmake file)
    # target mod date should be before goodmake file mod date
    # target md5 checksum should match goodmake file checksum

    # echo $BUILD_DATE $TGT_DATE $REM_DATE
    # echo $BUILD_SUM $TGT_SUM

    if [ "$TGT_SUM" != "$BUILD_SUM" ]; then
        echo "$TARGET" changed since GoodMake build
    elif [ "$TGT_DATE" -lt "$BUILD_DATE" ]; then
        echo "$TARGET" pre-dates GoodMake build
    elif [ "$TGT_DATE" -gt "$REM_DATE" ]; then
        echo "$TARGET" modified after GoodMake check
    else
        $RM "$REM"
        $RM "$TARGET"
    fi
done

rm "$CURRENT"
