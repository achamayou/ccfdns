# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the Apache 2.0 License.

import sys
import cbor2
import cwt
import json
import base64
import snp_pytools
from cryptography import x509
from cryptography.hazmat.backends import default_backend

def string_to_cert(pem_string):
    return x509.load_pem_x509_certificate(pem_string.encode(), default_backend())

def verify_attestation(attestation_cbor):
    # Extract certs from cbor and pass them to avoid AMD access
    cert_chain = json.loads(base64.b64decode(attestation_cbor["eds"]))
    vceck = cert_chain['vcekCert']
    chain = cert_chain['certificateChain'].split("-----END CERTIFICATE-----\n")
    certificates = {
        'ark': string_to_cert(chain[1] + "-----END CERTIFICATE-----\n"),
        'ask': string_to_cert(chain[0] + "-----END CERTIFICATE-----\n"),
        'vcek': string_to_cert(vceck),
    }
    report, certs, report_data_hex = snp_pytools.verify_attestation_bytes(attestation_cbor["att"], processor_model="milan", certificates=certificates, certificates_path="ca")
    #report, certs, report_data_hex = snp_pytools.verify_attestation_bytes(attestation_cbor["att"], processor_model="milan")
    print(report.host_data)
    print(report_data_hex)
    print(report.measurement)
    # cose_ctx = cwt.COSE.new()
    # UVM descriptor check
    # Return platform & UVM descriptor in a format Rego can use

if __name__ == "__main__":
    with open(sys.argv[1], "rb") as f:
        attestation_cbor = cbor2.load(f)

    verify_attestation(attestation_cbor)