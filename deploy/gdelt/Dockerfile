# python:3.12-slim multi-platform index, reviewed 2026-09-15.  Keep the tag
# for readability but pin it so --pull=false cannot silently select a changed
# base image.  The installer includes this Dockerfile in its build-input hash.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea
WORKDIR /opt/forex
# Keep Docker's COPY set identical to the installer build-input manifest.
# This module is deliberately dependency-free, so copying the whole application
# package would make its identity depend on unrelated Forex changes.
COPY src/forex/gdelt_publisher_egress.py /opt/forex/forex/gdelt_publisher_egress.py
COPY scripts/run_gdelt_publisher_egress.py /opt/forex/run.py
ENV PYTHONPATH=/opt/forex
LABEL org.opencontainers.image.title="forex-gdelt-publisher-egress"
LABEL org.opencontainers.image.description="Bounded publisher retrieval; no trading authority"
USER 65532:65532
ENTRYPOINT ["python3", "/opt/forex/run.py"]
