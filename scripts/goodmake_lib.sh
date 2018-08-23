# Useful varibles and functions for goodmake builds

make="$(readlink --canonicalize $0)"
make_dir="$(dirname $make)"
make_name="$(basename $0)"
make_every="$(which goodmake_every.sh)"

# Execute a command in the script directory, instead of PWD.
make_global() { cd "$make_dir"; $make "$@"; cd -; }

# Echo the command before executing
make_log() { echo "+" "$@"; "$@"; }
