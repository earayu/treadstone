import logging
import subprocess
from importlib import resources


class XrandrError(Exception):
    """Custom exception for xrandr related errors."""

    pass


def _generate_exact_modeline(
    width: int, height: int, refresh_rate: float = 60.0
) -> tuple[str, str]:
    """
    Generates a precise xrandr modeline for a given resolution and refresh rate.

    Returns:
        A tuple containing (mode_name, modeline_params_string).
        The mode_name is in the standard "WIDTHxHEIGHT" format.
    """
    # The mode name should be the standard format to match system-defined modes.
    mode_name = f"{width}x{height}"

    # 1. Define simplified timing parameters
    h_sync_start = width + 16
    h_sync_end = h_sync_start + 96
    h_total = h_sync_end + 48

    v_sync_start = height + 3
    v_sync_end = v_sync_start + 5
    v_total = v_sync_end + 20

    # 2. Calculate the required pixel clock in MHz
    pclk_hz = h_total * v_total * refresh_rate
    pclk_mhz = pclk_hz / 1_000_000

    # 3. Format the modeline parameters into a single string
    modeline_params = (
        f"{pclk_mhz:.2f} "
        f"{width} {h_sync_start} {h_sync_end} {h_total} "
        f"{height} {v_sync_start} {v_sync_end} {v_total} "
        "+hsync +vsync"
    )

    return mode_name, modeline_params


def set_resolution(width: int, height: int) -> str:
    """
    Calculates a precise 60Hz modeline and calls the set-resolution.sh script
    to apply it. It uses a standard "WIDTHxHEIGHT" mode name for compatibility.

    Args:
        width: The target width.
        height: The target height.

    Returns:
        A success message extracted from the script's output.

    Raises:
        XrandrError: If the script fails or is not found.
    """
    try:
        mode_name, modeline_params = _generate_exact_modeline(width, height)
        logging.info(
            f"Using standard mode name '{mode_name}' with "
            f"calculated modeline: {modeline_params}"
        )

        with resources.path("gem.scripts", "set-resolution.sh") as script_path:
            command = [str(script_path), mode_name, modeline_params]
            logging.info(f"Executing command: {' '.join(command)}")

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                check=True,
                encoding="utf-8",
            )

        success_message = ""
        for line in result.stdout.strip().split("\n"):
            if line.startswith("Success:"):
                success_message = line.replace("Success: ", "")

        if not success_message:
            success_message = (
                "Resolution script executed successfully, but no success message found."
            )

        logging.info(f"Script output: {result.stdout.strip()}")
        return success_message

    except FileNotFoundError as e:
        raise XrandrError(f"Script 'set-resolution.sh' not found. Original error: {e}")
    except subprocess.CalledProcessError as e:
        error_output = e.stderr.strip()
        logging.error(
            f"Script failed with exit code {e.returncode}. Stderr: {error_output}"
        )
        raise XrandrError(f"Failed to set resolution. Reason: {error_output}")
