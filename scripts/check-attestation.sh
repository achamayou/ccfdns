#!/bin/bash
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache 2.0 License.

set -e

if [ ! -f "scripts/env/bin/activate" ]
    then
        python3 -m venv scripts/env
fi

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null)"

source scripts/env/bin/activate
pip install --upgrade -q pip
pip install -q git+https://github.com/TEE-Attestation/snp_pytools.git@f3422d9e06ed0dc091a075e5878b2631be464a79
pip install -q -e $REPO_ROOT/python

python3 -c "import snp_pytools; print(dir(snp_pytools))"