#!/usr/bin/env bash

# REQUIRES: preload
# RUN: bash %s %T/clean_env_build
# RUN: cd %T/clean_env_build; %{intercept-build} --cdb result.json env - ./run.sh
# RUN: cd %T/clean_env_build; cdb_diff result.json expected.json

set -o errexit
set -o nounset
set -o xtrace

# the test creates a subdirectory inside output dir.
#
# ${root_dir}
# ├── run.sh
# ├── expected.json
# └── src
#    └── empty.c

clang=$(command -v ${CC})
clangpp=$(command -v ${CXX})

root_dir=$1
mkdir -p "${root_dir}/src"

touch "${root_dir}/src/empty.c"

build_file="${root_dir}/run.sh"
cat >> ${build_file} << EOF
#!/usr/bin/env bash

set -o nounset
set -o xtrace

${clang} -c -o src/empty.o -Dver=1 src/empty.c;
${clangpp} -c -o src/empty.o -Dver=2 src/empty.c;

cd src
${clang} -c -o empty.o -Dver=3 empty.c;
${clangpp} -c -o empty.o -Dver=4 empty.c;

true;
EOF
chmod +x ${build_file}

cat >> "${root_dir}/expected.json" << EOF
[
{
  "command": "cc -c -o src/empty.o -Dver=1 src/empty.c",
  "directory": "${root_dir}",
  "file": "src/empty.c"
}
,
{
  "command": "c++ -c -o src/empty.o -Dver=2 src/empty.c",
  "directory": "${root_dir}",
  "file": "src/empty.c"
}
,
{
  "command": "cc -c -o empty.o -Dver=3 empty.c",
  "directory": "${root_dir}/src",
  "file": "empty.c"
}
,
{
  "command": "c++ -c -o empty.o -Dver=4 empty.c",
  "directory": "${root_dir}/src",
  "file": "empty.c"
}
]
EOF
