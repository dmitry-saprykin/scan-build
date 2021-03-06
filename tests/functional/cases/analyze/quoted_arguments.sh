#!/usr/bin/env bash

# RUN: bash %s %T/quoted_arguments
# RUN: cd %T/quoted_arguments; %{scan-build} -o . --status-bugs --intercept-first ./run.sh
# RUN: cd %T/quoted_arguments; %{scan-build} -o . --status-bugs --intercept-first  --override-compiler ./run.sh
# RUN: cd %T/quoted_arguments; %{scan-build} -o . --status-bugs --override-compiler ./run.sh

set -o errexit
set -o nounset
set -o xtrace

# the test creates a subdirectory inside output dir.
#
# ${root_dir}
# ├── run.sh
# └── src
#    └── names.c

root_dir=$1
mkdir -p "${root_dir}/src"

cat >> "${root_dir}/src/names.c" << EOF
char const * const first = FIRST;
char const * const last = LAST;

#include <stdio.h>

int main() {
  printf("hi %s %s, how are you?\n", first, last);
  return 0;
}
EOF

build_file="${root_dir}/run.sh"
cat >> ${build_file} << EOF
#!/usr/bin/env bash

set -o nounset
set -o xtrace

"\$CC" ./src/names.c -o names -DFIRST=\"Sir\ John\" -DLAST="\"Smith Dr\"";
./names | grep "hi Sir John Smith Dr, how are you?"
EOF
chmod +x ${build_file}
