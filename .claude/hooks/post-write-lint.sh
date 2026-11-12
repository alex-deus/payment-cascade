#!/bin/bash

if [[ "$CLAUDE_TOOL_FILE" == *.py ]]; then
  ruff format
fi
