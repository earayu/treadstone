#!/bin/bash

# Declare the array that will hold the final list of ports to check.
PORTS_ARRAY=()

# The logic forks here:
# 1. If WAIT_PORTS is provided, we process it as a string override.
# 2. If WAIT_PORTS is not provided, we build the array directly from individual variables.
if [ -n "$WAIT_PORTS" ]; then
  # Case 1: WAIT_PORTS is set, so it overrides the individual variables.

  # If /opt/gem/mcp.disabled does exist, remove port 8089 from the wait list.
  # This is done after setting WAIT_PORTS to handle both default and environment-provided values.
  if [ -f /opt/gem/mcp.disabled ]; then
    if [ -n "$MCP_SERVER_PORT" ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - /opt/gem/mcp.disabled found, removing port $MCP_SERVER_PORT from wait list."
      # Use sed to robustly remove 8089 and its surrounding commas if they exist
      # 1. Remove '8089,' (for start/middle position)
      # 2. Remove ',8089' (for end position)
      # 3. Remove '8089' (if it's the only port in the list)
      WAIT_PORTS=$(echo "$WAIT_PORTS" | sed -e "s/$MCP_SERVER_PORT,//g" -e "s/,$MCP_SERVER_PORT//g" -e "s/^$MCP_SERVER_PORT$//g")
    fi
  fi

  # Convert the final, processed string to an array.
  IFS=',' read -ra PORTS_ARRAY <<<"$WAIT_PORTS"
else
  # Case 2: WAIT_PORTS is not set. Build the array directly.

  # Add ports to the array one by one, checking conditions as we go.
  [ -n "$GEM_SERVER_PORT" ] && PORTS_ARRAY+=("$GEM_SERVER_PORT")
  [ -n "$BROWSER_REMOTE_DEBUGGING_PORT" ] && PORTS_ARRAY+=("$BROWSER_REMOTE_DEBUGGING_PORT")

  # For the MCP port, only add it if the variable is set AND the conf file exists.
  if [ -n "$MCP_SERVER_PORT" ]; then
    if [ -f /opt/gem/mcp.disabled ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - /opt/gem/mcp.disabled found, removing port $MCP_SERVER_PORT from wait list."
    else
      PORTS_ARRAY+=("$MCP_SERVER_PORT")
    fi
  fi
fi

# Proceed only if there are ports in the final array.
if [ ${#PORTS_ARRAY[@]} -eq 0 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') - No ports to wait for. Proceeding directly."
else
  # The `(IFS=,; echo "${PORTS_ARRAY[*]}")` part joins the array elements with a comma for clean logging.
  echo "$(date '+%Y-%m-%d %H:%M:%S') - Waiting for services to be ready..."
  echo "Ports to check: $(
    IFS=,
    echo "${PORTS_ARRAY[*]}"
  )"
  echo "Timeout: ${WAIT_TIMEOUT}s, Check interval: ${WAIT_INTERVAL}s"

  # Record start time
  start_time=$(date +%s)

  # Main loop
  while true; do
    all_ready=true

    for port in "${PORTS_ARRAY[@]}"; do
      # Remove leading/trailing whitespace
      port=$(echo "$port" | xargs)

      # This check is robust in case the array contains empty elements, e.g., from "8088,,9222"
      if [ -z "$port" ]; then
        continue
      fi

      if ! nc -z localhost "$port" >/dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') - Waiting for localhost:$port..."
        all_ready=false
        break
      fi
    done

    if [ "$all_ready" = true ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - All services are ready!"
      break
    fi

    # Check timeout
    current_time=$(date +%s)
    elapsed=$((current_time - start_time))
    if [ $elapsed -ge $WAIT_TIMEOUT ]; then
      echo "$(date '+%Y-%m-%d %H:%M:%S') - Timeout after ${WAIT_TIMEOUT}s waiting for services"
      exit 1
    fi

    sleep $WAIT_INTERVAL
  done
fi

# Start nginx
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting nginx..."
exec /usr/sbin/nginx -c /opt/gem/nginx.conf -g 'daemon off;'
