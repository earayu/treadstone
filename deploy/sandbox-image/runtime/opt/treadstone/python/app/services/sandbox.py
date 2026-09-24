import getpass
import logging
import os
import shutil
from typing import Any, Dict

from app.models.sandbox import (
    AvailableTool,
    RuntimeEnv,
    SandboxDetail,
    SandboxInfo,
    SystemEnv,
    ToolCategory,
    ToolSpec,
)
from app.utils import (
    get_listening_ports,
    get_system_info,
    resolve_cmd_info,
)


logger = logging.getLogger(__name__)


class SandboxService:
    def __init__(self):
        pass

    def get_sandbox_info(self) -> SandboxInfo:
        # 获取系统信息
        sys_info = get_system_info()

        user = getpass.getuser() or os.environ.get('USER')

        occupied_ports = get_listening_ports()

        image_version = os.environ.get('IMAGE_VERSION', '')
        home_dir = f'/home/{os.environ.get("USER")}'

        python3_12 = resolve_cmd_info('python3')
        nodejs = resolve_cmd_info('node')

        detail = SandboxDetail(
            system=SystemEnv(
                os=sys_info['os'],
                os_version=sys_info['os_version'],
                arch=sys_info['arch'],
                user=user,
                home_dir=home_dir,
                timezone=os.environ.get('TZ') or '',
                occupied_ports=occupied_ports,
            ),
            runtime=RuntimeEnv(
                python=[
                    ToolSpec(
                        ver=python3_12.version,
                        bin=str(python3_12.bin),
                        alias=['python', 'python3', 'python3.12', 'pip', 'pip3'],
                    ),
                ],
                nodejs=[
                    ToolSpec(
                        ver=nodejs.version,
                        bin=str(nodejs.bin),
                        alias=[],
                    )
                ],
            ),
            utils=[
                ToolCategory(
                    category='Text editors',
                    tools=[AvailableTool(name=tool) for tool in ['vim', 'nano']],
                ),
                ToolCategory(
                    category='File operations',
                    tools=[
                        AvailableTool(name=tool)
                        for tool in [
                            'wget',
                            'curl',
                            'tar',
                            'zip',
                            'unzip',
                            'tree',
                            'rsync',
                            'lsyncd',
                        ]
                    ],
                ),
                ToolCategory(
                    category='Development',
                    tools=[AvailableTool(name=tool) for tool in ['git', 'gh', 'uv']],
                ),
                ToolCategory(
                    category='Network tools',
                    tools=[
                        AvailableTool(name=tool)
                        for tool in ['ping', 'telnet', 'netcat', 'nmap']
                    ],
                ),
                ToolCategory(
                    category='Text processing',
                    tools=[
                        AvailableTool(
                            name=tool[0] if isinstance(tool, list) else tool,
                            description=tool[1] if isinstance(tool, list) else '',
                        )
                        for tool in ['grep', 'sed', 'awk', 'jq', ['rg', 'ripgrep']]
                    ],
                ),
                ToolCategory(
                    category='System monitoring',
                    tools=[AvailableTool(name=tool) for tool in ['htop', 'procps']],
                ),
            ],
        )
        for category in detail.utils:
            category.tools = [tool for tool in category.tools if shutil.which(tool.name)]
        detail.utils = [category for category in detail.utils if category.tools]
        python_str = '\n'.join(
            [f'- {spec.ver}(path: {spec.bin})' for spec in detail.runtime.python]
        )
        nodejs_str = '\n'.join(
            [f'- {spec.ver}(path: {spec.bin})' for spec in detail.runtime.nodejs]
        )
        tools_str = '\n'.join(
            [
                f'- {cat.category}: {", ".join([tool.name for tool in cat.tools])}'
                for cat in detail.utils
            ]
        )

        info = f"""## System Environment{
            f' (v{image_version})' if image_version else ''
        }:
- {detail.system.os} {detail.system.os_version} ({detail.system.arch})
- User: {detail.system.user} (unprivileged)
- Home directory: {detail.system.home_dir}
- Timezone: {detail.system.timezone}
- Occupied Ports: {','.join(occupied_ports)}

## Development Environment:
Python:
{python_str}

Node.js:
{nodejs_str}

## Available Tools:
{tools_str}
"""

        return SandboxInfo(
            home_dir=home_dir, version=image_version, detail=detail, info=info
        )

    def generate_llms_txt(self, openapi_schema: Dict[str, Any]) -> str:
        sandbox_info = self.get_sandbox_info()
        return f'{sandbox_info.info}\n'
