# Useful varibles and functions for goodmake builds

rem="$(readlink --canonicalize $0)"
rem_dir="$(dirname $rem)"
rem_name="$(basename $0)"

global() { cd "$rem_dir"; $rem "$@"; cd -; }
