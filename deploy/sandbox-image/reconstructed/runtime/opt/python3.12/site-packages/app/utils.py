import logging
import os
import platform
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path
from typing import List, Set

from pydantic import BaseModel


logger = logging.getLogger(__name__)


def normalize_cwd(cwd):
    """标准化 cwd 路径，支持相对路径"""

    if not cwd:
        return None

    cwd = os.path.expanduser(cwd)
    cwd = os.path.abspath(cwd)
    return cwd


def get_system_info() -> dict:
    """获取系统环境信息"""
    import distro

    info = {
        'os': distro.name(pretty=True) or platform.system(),
        'os_version': distro.version(best=True) or platform.release(),
        'arch': platform.machine(),
        'platform': platform.platform(),
    }
    return info


def get_command_version(command: str) -> str:
    """获取命令版本信息"""
    try:
        result = subprocess.run(
            [command, '--version'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip().split('\n')[0]
        return 'Not available'
    except (subprocess.TimeoutExpired, FileNotFoundError, subprocess.SubprocessError):
        return 'Not available'


def _run(args: list[str], timeout: float = 2.0) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr or '').strip()
    except Exception:
        return ''


class CmdInfo(BaseModel):
    bin: Path | None
    version: str | None


def resolve_cmd_info(cmd: str) -> CmdInfo:
    """
    输入命令名（如 'python3.12' / 'python3.11' / 'git'），
    返回 {'bin': Path|None, 'version': str|None}
    - bin 为 realpath（若能解析）
    - version 优先用 '<cmd> --version' 的首行，失败则 None
    """
    p = shutil.which(cmd)
    if not p:
        return CmdInfo(bin=None, version=None)

    # realpath（去掉软链）
    try:
        bin_path = Path(os.path.realpath(p))
    except Exception:
        bin_path = Path(p).resolve()

    # 常见版本旗标：先 '--version'，若空再 '-V'
    ver = _run([p, '--version']) or _run([p, '-V'])
    ver = ver.splitlines()[0] if ver else None

    return CmdInfo(bin=bin_path, version=ver)


def get_node_version() -> str:
    """获取 Node.js 版本"""
    return get_command_version('node')


def get_npm_version() -> str:
    """获取 npm 版本"""
    return get_command_version('npm')


def get_bc_version() -> str:
    """获取 bc 版本"""
    return get_command_version('bc')


def get_listening_ports() -> List[str]:
    ports: Set[int] = set()
    try:
        import psutil

        for c in psutil.net_connections(kind='tcp'):
            if getattr(c, 'status', None) == psutil.CONN_LISTEN and getattr(
                c, 'laddr', None
            ):
                ports.add(str(c.laddr.port))
        for c in psutil.net_connections(kind='udp'):
            la = getattr(c, 'laddr', None)
            if la:
                ports.add(str(la.port))
    except Exception:
        pass
    return sorted(ports)


def deep_merge(target, source):
    """deep merge dict, not overwrite existing keys"""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge(target[key], value)
        else:
            target[key] = deepcopy(value)
    return target


def normalize_path_prefix(prefix: str | None) -> str:
    """
    Normalize X-Forwarded-Prefix header value for URL construction.

    Args:
        prefix: The path prefix from X-Forwarded-Prefix header

    Returns:
        Normalized prefix string:
        - Empty string if prefix is None or empty
        - Starts with '/' and does not end with '/'
        - e.g., '/api/v1', '/proxy'

    Examples:
        >>> normalize_path_prefix(None)
        ''
        >>> normalize_path_prefix('')
        ''
        >>> normalize_path_prefix('/api/v1')
        '/api/v1'
        >>> normalize_path_prefix('/api/v1/')
        '/api/v1'
        >>> normalize_path_prefix('api/v1')
        '/api/v1'
        >>> normalize_path_prefix('api/v1/')
        '/api/v1'
    """
    if not prefix:
        return ''

    # Remove leading and trailing whitespace
    prefix = prefix.strip()

    if not prefix:
        return ''

    # Ensure starts with '/'
    if not prefix.startswith('/'):
        prefix = '/' + prefix

    # Remove trailing '/'
    if prefix.endswith('/'):
        prefix = prefix.rstrip('/')

    return prefix


def is_binary(filename):
    """
    :param filename: File to check.
    :returns: True if it's a binary file, otherwise False.
    """
    from binaryornot.helpers import get_starting_chunk, is_binary_string

    logger.debug('is_binary: %(filename)r', locals())

    # Check if the file extension is in a list of known binary types
    binary_extensions = [
        '.pyc',
    ]
    for ext in binary_extensions:
        if filename.endswith(ext):
            return True

    text_extensions = ['.md', '.mdx', '.txt', '.py']
    for ext in text_extensions:
        if filename.endswith(ext):
            return False

    # Check if the starting chunk is a binary string
    chunk = get_starting_chunk(filename, length=1024)
    return is_binary_string(chunk)
