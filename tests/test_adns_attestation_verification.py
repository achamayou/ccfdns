# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache 2.0 License.

import sys
import cbor2
import snp_pytools

def verify_attestation(attestation_cbor):
    # Extract certs from cbor and pass them to avoid AMD access
    report, certs, report_data_hex = snp_pytools.verify_attestation_bytes(attestation_cbor["att"], processor_model="milan")
    print(report.host_data)
    print(report_data_hex)
    # UVM descriptor check
    # Return platform & UVM descriptor in a format Rego can use

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as f:
        attestation_cbor = cbor2.load(f)

    verify_attestation(attestation_cbor)