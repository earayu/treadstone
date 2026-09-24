import json
import subprocess
from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException

from app.core.service_container import services
from app.models.sandbox import SandboxDetail
from app.schemas.response import Response


if TYPE_CHECKING:
    from app.services.sandbox import SandboxService

router = APIRouter()


class SandboxResponse(Response):
    home_dir: str
    version: str
    detail: SandboxDetail


@router.get(
    '',
    response_model=SandboxResponse,
    openapi_extra={
        'x-fern-sdk-group-name': 'sandbox',
        'x-fern-sdk-method-name': 'get_context',
    },
)
async def get_sandbox_context():
    """
    Get sandbox environment information
    """
    try:
        sandbox_service: 'SandboxService' = services.get('sandbox_service')
        sandbox_info = sandbox_service.get_sandbox_info()

        return SandboxResponse(
            success=True,
            message='Environment information retrieved',
            data=sandbox_info.info,
            detail=sandbox_info.detail.model_dump(),
            version=sandbox_info.version,
            home_dir=sandbox_info.home_dir,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'An unexpected error occurred: {e}'
        )


@router.get(
    '/packages/python',
    response_model=Response,
    openapi_extra={
        'x-fern-sdk-group-name': 'sandbox',
        'x-fern-sdk-method-name': 'get_python_packages',
    },
)
async def python_packages():
    """
    Get installed packages by language
    """
    try:
        python_packages = get_python_packages()

        return Response(
            success=True, message='Packages information retrieved', data=python_packages
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'An unexpected error occurred: {e}'
        )


@router.get(
    '/packages/nodejs',
    response_model=Response,
    openapi_extra={
        'x-fern-sdk-group-name': 'sandbox',
        'x-fern-sdk-method-name': 'get_nodejs_packages',
    },
)
async def nodejs_packages():
    """
    Get installed packages by language
    """
    try:
        nodejs_packages = get_node_packages()

        packages_info = f"""Node.js Packages:
{nodejs_packages}
"""

        return Response(
            success=True, message='Packages information retrieved', data=packages_info
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f'An unexpected error occurred: {e}'
        )


def get_python_packages() -> str:
    """获取已安装的Python包信息"""
    try:
        result = subprocess.run(
            ['pip', 'list', '--format=json'], stdout=subprocess.PIPE
        )
        packages = ''

        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return (
                '\n'.join(
                    map(lambda pkg: f'  - {pkg["name"]}=={pkg["version"]}', packages)
                )
                if packages
                else '  - No global packages installed'
            )

        else:
            return '  - No global packages installed'
    except Exception:
        return '  - Unable to retrieve package list'


def get_node_packages() -> str:
    """获取已安装的Node.js包信息"""
    try:
        # 检查是否有全局安装的npm包
        result = subprocess.run(
            ['npm', 'list', '-g', '--depth=0'],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            packages = []
            for line in lines[1:]:  # 跳过标题行
                if line.strip() and not line.startswith('npm ERR'):
                    # 解析npm list的输出格式
                    if '├──' in line or '└──' in line:
                        parts = line.split()
                        if len(parts) >= 2:
                            package_name = parts[1]
                            version = (
                                parts[2].strip('@') if len(parts) > 2 else 'unknown'
                            )
                            packages.append(f'  - {package_name}@{version}')

            if packages:
                return '\n'.join(packages)
            else:
                return '  - No global packages installed'
        return '  - Unable to retrieve package list'
    except Exception:
        return '  - Unable to retrieve package list'


def check_network_connectivity() -> str:
    """检查网络连接状态"""
    try:
        # 测试DNS解析
        result = subprocess.run(
            ['nslookup', 'google.com'], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return '- Internet connectivity: Available'
        else:
            return '- Internet connectivity: Limited (DNS issues)'
    except Exception:
        return '- Internet connectivity: Unknown'
