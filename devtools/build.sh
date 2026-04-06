#!/bin/bash

BIN=$(realpath -s ./bin)
DIST=$(realpath -s ./_dist)
SPECS=$(realpath -s ./_specs)
BUILD=$(realpath -s ./_build)

mkdir -p $BIN

function pyinstall {
    pyinstaller --distpath $DIST --workpath $BUILD --specpath $SPECS -F -p ./src $@
}

# cfscripts linux
pyinstall -n cfscripts src/cfscripts/cli.py
cp $DIST/cfscripts $BIN/cfscripts
