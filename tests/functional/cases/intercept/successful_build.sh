#!/usr/bin/env bash

# RUN: bash %s %T/successful_build
# RUN: cd %T/successful_build; %{intercept-build} --cdb wrapper.json --override-compiler ./run.sh
# RUN: cd %T/successful_build; cdb_diff wrapper.json expected.json
#
# when library preload disabled, it falls back to use compiler wrapper
#
# RUN: cd %T/successful_build; %{intercept-build} --cdb preload.json ./run.sh
# RUN: cd %T/successful_build; cdb_diff preload.json expected.json

set -o errexit
set -o nounset
set -o xtrace

# the test creates a subdirectory inside output dir.
#
# ${root_dir}
# ├── run.sh
# ├── expected.json
# └── src
#    ├── empty.s
#    └── empty.c

root_dir=$1
mkdir -p "${root_dir}/src"

touch "${root_dir}/src/empty.s"
touch "${root_dir}/src/empty.c"

build_file="${root_dir}/run.sh"
cat >> ${build_file} << EOF
#!/usr/bin/env bash

set -o nounset
set -o xtrace

"\$CC" -c -o src/empty.o -Dver=1 src/empty.c;
"\$CXX" -c -o src/empty.o -Dver=2 src/empty.c;
"\$CC" -c -o src/empty.o -x assembler-with-cpp src/empty.s;

cd src
"\$CC" -c -o empty.o -Dver=3 empty.c;
"\$CXX" -c -o empty.o -Dver=4 empty.c;

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
  "command": "cc -c -o src/empty.o -x assembler-with-cpp src/empty.s",
  "directory": "${root_dir}",
  "file": "src/empty.s"
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
