#!/bin/bash
# Optional workaround for networks with a TLS-intercepting proxy (corporate
# proxy, cloud sandbox...). Rebuilds the base image locally, under the SAME
# tag, with an extra CA trusted by apt/pip/npm/curl. The task Dockerfile is
# left untouched: `docker build` picks the local tag instead of pulling.
#
# When OS package mirrors are blocked too, pass a fuller source image that
# already ships the needed tools (e.g. python:3.12, which includes git); the
# result is still tagged as base_image.
#
# Usage: scripts/build_ca_base_image.sh /path/to/ca.crt [base_image] [source_image]
set -euo pipefail

ca_file="${1:?usage: $0 /path/to/ca.crt [base_image] [source_image]}"
base_image="${2:-python:3.12-slim}"
source_image="${3:-${base_image}}"

build_dir="$(mktemp -d)"
trap 'rm -rf "${build_dir}"' EXIT

cp "${ca_file}" "${build_dir}/extra-ca.crt"
cat > "${build_dir}/Dockerfile" <<DOCKERFILE
FROM ${source_image}
COPY extra-ca.crt /usr/local/share/ca-certificates/extra-ca.crt
RUN update-ca-certificates \\
    && if [ -f /etc/apt/sources.list.d/debian.sources ]; then \\
         sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources; \\
       fi
ENV SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt \\
    REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \\
    PIP_CERT=/etc/ssl/certs/ca-certificates.crt \\
    CURL_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt \\
    NODE_EXTRA_CA_CERTS=/etc/ssl/certs/ca-certificates.crt
DOCKERFILE

docker pull "${source_image}"
docker build -t "${base_image}" "${build_dir}"
echo "Tagged ${base_image} (from ${source_image}) with extra CA from ${ca_file}"
