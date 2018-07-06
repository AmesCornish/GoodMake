# Useful varibles and functions for goodmake builds

gm="$(readlink --canonicalize $0)"
gm_dir="$(dirname $gm)"
gm_name="$(basename $0)"

# Execute a command in the script directory, instead of PWD.
gm_global() { cd "$gm_dir"; $gm "$@"; cd -; }

# Echo the command before executing
gm_log() { echo "+" "$@"; "$@"; }
