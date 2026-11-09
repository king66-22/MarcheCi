#!/usr/bin/env sh
exec "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/marcheci.sh" stop "$@"
