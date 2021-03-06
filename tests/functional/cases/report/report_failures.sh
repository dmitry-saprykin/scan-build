#!/usr/bin/env bash

# RUN: bash %s %T/report_failures
# RUN: cd %T/report_failures; %{analyze-build} --output . --keep-empty --cdb input.json | ./check_exists.sh
# RUN: cd %T/report_failures; %{analyze-build} --no-failure-reports --output . --keep-empty --cdb input.json | ./check_not_exists.sh
#
# RUN: cd %T/report_failures; %{analyze-build} --output . --keep-empty --plist-html --cdb input.json | ./check_exists.sh
# RUN: cd %T/report_failures; %{analyze-build} --no-failure-reports --output . --keep-empty --plist-html --cdb input.json | ./check_not_exists.sh
#
# RUN: cd %T/report_failures; %{analyze-build} --output . --keep-empty --plist --cdb input.json | ./check_exists.sh
# RUN: cd %T/report_failures; %{analyze-build} --no-failure-reports --output . --keep-empty --plist --cdb input.json | ./check_not_exists.sh

set -o errexit
set -o nounset
set -o xtrace

# the test creates a subdirectory inside output dir.
#
# ${root_dir}
# ├── input.json
# ├── check_exists.sh
# ├── check_not_exists.sh
# └── src
#    └── broken.c

root_dir=$1
mkdir -p "${root_dir}/src"

cp "${test_input_dir}/compile_error.c" "${root_dir}/src/broken.c"

cat >> "${root_dir}/input.json" << EOF
[
    {
        "directory": "${root_dir}",
        "file": "${root_dir}/src/broken.c",
        "command": "cc -c -o src/broken.o src/broken.c"
    }
]
EOF

check_one="${root_dir}/check_exists.sh"
cat >> "${check_one}" << EOF
#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o xtrace

out_dir=\$(sed -n 's/\(.*\) Report directory created: \(.*\)/\2/p')
if [ ! -d "\$out_dir" ]
then
    echo "output directory should exists"
    false
else
    if [ ! -d "\$out_dir/failures" ]
    then
        echo "failure directory should exists"
        false
    fi
fi
EOF
chmod +x "${check_one}"

check_two="${root_dir}/check_not_exists.sh"
cat >> "${check_two}" << EOF
#!/usr/bin/env bash

set -o errexit
set -o nounset
set -o xtrace

out_dir=\$(sed -n 's/\(.*\) Report directory created: \(.*\)/\2/p')
if [ ! -d "\$out_dir" ]
then
    echo "output directory should exists"
    false
else
    if [ -d "\$out_dir/failures" ]
    then
        echo "failure directory should not exists"
        false
    fi
fi
EOF
chmod +x "${check_two}"
