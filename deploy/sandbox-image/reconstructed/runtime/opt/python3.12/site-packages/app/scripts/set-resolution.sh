#!/bin/bash

# A script to set screen resolution strictly following the "query before acting" principle.
# It avoids '|| true' and performs explicit checks before modifying state.

# Exit immediately if any command fails.
set -e

# --- Argument check ---
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <mode_name> \"<modeline_parameters>\"" >&2
  exit 1
fi

MODE_NAME="$1"
MODELINE_PARAMS="$2"

# --- Main logic ---

# 1. Find the primary connected display.
DISPLAY_NAME=$(xrandr | grep ' connected' | head -n 1 | awk '{print $1}')
if [ -z "$DISPLAY_NAME" ]; then
  echo "Error: No connected display found." >&2
  exit 2
fi
echo "Info: Found connected display: $DISPLAY_NAME"

# 2. Check if the mode needs to be created.
# A mode needs to be created if its name doesn't appear anywhere in the output.
# We use grep with '-q' for a silent check.
if ! xrandr | grep -q "^\s*${MODE_NAME}\s"; then
  echo "Info: Mode '$MODE_NAME' definition not found. Creating it..."
  xrandr --newmode "$MODE_NAME" $MODELINE_PARAMS

  # After creating a mode, it must be added. We don't need a separate check for addmode.
  # The most direct and logical step is to add it immediately.
  echo "Info: Adding newly created mode '$MODE_NAME' to display '$DISPLAY_NAME'..."
  xrandr --addmode "$DISPLAY_NAME" "$MODE_NAME"
fi

# 3. Apply the final resolution.
echo "Info: Attempting to set resolution to $MODE_NAME on $DISPLAY_NAME..."
# At this point, all prerequisites are met. Any failure here is a genuine error.
if ! xrandr --output "$DISPLAY_NAME" --mode "$MODE_NAME"; then
  echo "Error: The final xrandr command failed to set mode ${MODE_NAME}." >&2
  echo "Error: This could be due to hardware limitations or an invalid modeline." >&2
  exit 3
fi

echo "Success: Display ${DISPLAY_NAME} resolution set to ${MODE_NAME}."
exit 0
