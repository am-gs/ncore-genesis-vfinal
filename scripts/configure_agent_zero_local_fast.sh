#!/usr/bin/env bash
# DEPRECATED: This script is for legacy Ollama-local configuration.
# Use configure_agent_zero_external.sh instead, which routes Agent Zero
# through Bifrost v2 (external GPU providers at port 8000).
set -Eeuo pipefail
IFS=$'\n\t'

>&2 echo "ERROR: configure_agent_zero_local_fast.sh is deprecated."
>&2 echo "       Ollama has been removed from the NCore stack."
>&2 echo "       Use configure_agent_zero_external.sh instead."
exit 1
