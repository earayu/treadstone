"""
OpenHands-based Shell Service Implementation
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Optional

from vendors.openhands.runtime.utils.bash import BashSession


if TYPE_CHECKING:
    from vendors.openhands.events.observation.commands import CmdOutputObservation


from app.models.shell import (
    ActiveShellSessionsResult,
    BashCommandStatus,
    ConsoleRecord,
    OpenHandsShellSession,
    ShellCommandResult,
    ShellSessionInfo,
    ShellViewResult,
)
from app.schemas.shell import ShellSessionStats


logger = logging.getLogger(__name__)


def strip_ansi_codes(text: str) -> str:
    """Remove ANSI escape sequences from text"""
    # ANSI escape sequence pattern
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    # Remove ANSI codes
    clean_text = ansi_escape.sub('', text)
    # Remove backspace characters and handle them
    clean_text = re.sub(r'.\x08', '', clean_text)
    # Remove carriage returns that aren't followed by newlines
    clean_text = re.sub(r'\r(?!\n)', '', clean_text)
    return clean_text


def map_openhands_status(observation: 'CmdOutputObservation') -> BashCommandStatus:
    """Map OpenHands observation to our status enum"""
    metadata = getattr(observation, 'metadata', None)
    suffix = getattr(metadata, 'suffix', '') if metadata else ''
    suffix_lower = suffix.lower()
    content_lower = getattr(observation, 'content', '').lower()

    if 'no new output' in suffix_lower or 'no new output' in content_lower:
        return BashCommandStatus.NO_CHANGE_TIMEOUT
    if 'timed out' in suffix_lower or 'timed out' in content_lower:
        return BashCommandStatus.HARD_TIMEOUT

    exit_code = getattr(observation, 'exit_code', None)

    if exit_code == 0:
        return BashCommandStatus.COMPLETED

    if exit_code == -1:
        terminated_markers = ['terminated', 'killed', 'not executed']
        if any(marker in suffix_lower for marker in terminated_markers) or any(
            marker in content_lower for marker in terminated_markers
        ):
            return BashCommandStatus.TERMINATED
        if getattr(observation, 'success', None) is False:
            return BashCommandStatus.TERMINATED
        return BashCommandStatus.TERMINATED

    if isinstance(exit_code, int):
        # 非零退出码仍然视为 completed (命令执行完成，只是有错误)
        return BashCommandStatus.COMPLETED

    if 'timeout' in content_lower:
        return BashCommandStatus.HARD_TIMEOUT

    return BashCommandStatus.COMPLETED


class OpenHandsShellManager:
    """基于 OpenHands BashSession 的 Shell 管理器"""

    def __init__(self):
        self.sessions: Dict[str, OpenHandsShellSession] = {}
        self._lock = asyncio.Lock()

        # 会话管理配置
        self.max_sessions = int(
            os.environ.get('MAX_SHELL_SESSIONS', 50)
        )  # 最大会话数，比 Jupyter 保守一些
        self.session_timeout = (
            3600  # 1小时超时，比 Jupyter 长一些因为shell会话可能长时间使用
        )

    async def _cleanup_expired_sessions(self):
        """清理过期的会话"""
        current_time = time.time()
        expired_sessions = []

        async with self._lock:
            for session_id, session in self.sessions.items():
                # 检查会话是否过期 (使用 last_used_at 时间戳)
                last_used_timestamp = session.last_used_at.timestamp()
                if current_time - last_used_timestamp > self.session_timeout:
                    expired_sessions.append(session_id)

        # 在锁外删除过期会话以避免死锁
        for session_id in expired_sessions:
            await self._force_delete_session(session_id, reason='expired')
            logger.info(f'Cleaned up expired session {session_id}')

    async def _force_delete_session(self, session_id: str, reason: str = 'cleanup'):
        """强制删除会话（内部使用，不检查锁）"""
        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            # 关闭 OpenHands session
            if session.bash_session:
                try:
                    session.bash_session.close()
                except Exception as e:
                    logger.warning(f'Error closing bash session during {reason}: {e}')

            # 清理订阅者
            session.char_subscribers.clear()
            session.line_subscribers.clear()

            # 从管理器中移除
            del self.sessions[session_id]
            session.active = False

            logger.info(f'Force deleted session {session_id} ({reason})')
            return True

    async def _enforce_session_limit(self):
        """强制会话数限制，移除最老的会话"""
        oldest_session_id = None

        async with self._lock:
            if len(self.sessions) >= self.max_sessions:
                # 找到最老的会话（最早的 last_used_at）
                oldest_session_id = min(
                    self.sessions.keys(), key=lambda k: self.sessions[k].last_used_at
                )

        # 在锁外删除以避免死锁
        if oldest_session_id:
            await self._force_delete_session(
                oldest_session_id, reason='evicted for limit'
            )
            logger.info(f'Evicted oldest session {oldest_session_id} to make room')

    async def create_session(
        self,
        session_id: Optional[str] = None,
        working_dir: Optional[str] = None,
        shell: str = '/bin/bash',
        environment: Optional[Dict[str, str]] = None,
    ) -> OpenHandsShellSession:
        """创建新的 shell 会话"""

        # 清理过期会话
        await self._cleanup_expired_sessions()

        # 强制会话数限制
        await self._enforce_session_limit()

        if session_id is None:
            session_id = str(uuid.uuid4())

        if working_dir is None:
            working_dir = os.environ.get('WORKSPACE', '/tmp')

        if environment is None:
            environment = {}

        try:
            bash_session = BashSession(
                work_dir=working_dir,
                username=os.environ.get('USER', 'gem'),
                no_change_timeout_seconds=120,
            )

            # 初始化 bash session
            bash_session.initialize()

            # 创建我们的会话包装器
            session = OpenHandsShellSession(
                id=session_id,
                working_dir=working_dir,
                bash_session=bash_session,
            )

            async with self._lock:
                self.sessions[session_id] = session

            logger.info(
                f'Created OpenHands shell session: {session_id} (total sessions: {len(self.sessions)})'
            )
            return session

        except Exception as e:
            logger.error(f'Failed to create session: {e}')
            raise

    async def execute_command(
        self,
        session_id: str,
        command: str,
        timeout: int = 30,
        async_mode: bool = False,
        working_dir: Optional[str] = None,
    ) -> ShellCommandResult:
        """执行命令"""

        session = self.get_session(session_id)
        if not session:
            raise ValueError(f'Session {session_id} not found')

        if not session.active:
            raise ValueError(f'Session {session_id} is not active')

        session.last_used_at = datetime.now()
        session.status = BashCommandStatus.RUNNING
        session.current_command = command

        command_to_run = command

        if working_dir:
            desired_dir = os.path.abspath(working_dir)
            if os.path.isdir(desired_dir):
                current_dir = (
                    os.path.abspath(session.working_dir)
                    if session.working_dir
                    else None
                )
                if current_dir != desired_dir:
                    command_to_run = f'cd {shlex.quote(desired_dir)} && {command}'
                session.working_dir = desired_dir
                if session.bash_session:
                    session.bash_session.work_dir = desired_dir
            else:
                logger.warning(
                    'Requested working directory does not exist: %s', working_dir
                )

        try:
            if async_mode:
                # 异步模式：立即返回，不等待结果
                asyncio.create_task(
                    self._execute_command_async(
                        session, command_to_run, timeout, display_command=command
                    )
                )

                return ShellCommandResult(
                    session_id=session_id,
                    command=command,
                    status=BashCommandStatus.RUNNING,
                    output=None,
                    console=None,
                )
            else:
                # 同步模式：等待执行完成
                return await self._execute_command_sync(
                    session, command_to_run, timeout, display_command=command
                )

        except Exception as e:
            session.status = BashCommandStatus.TERMINATED
            logger.error(f'Command execution failed: {e}')
            raise

    async def _execute_command_sync(
        self,
        session: OpenHandsShellSession,
        command: str,
        timeout: int,
        display_command: Optional[str] = None,
    ) -> ShellCommandResult:
        """同步执行命令（实际上在线程池中执行以避免阻塞）"""

        # 在线程池中执行以避免阻塞事件循环
        from vendors.openhands.events.action.commands import CmdRunAction

        visible_command = display_command or command

        loop = asyncio.get_event_loop()

        def _run_command():
            """在线程池中同步执行命令"""
            try:
                # 创建 OpenHands CmdRunAction
                action = CmdRunAction(command=command)

                # 执行命令
                observation = session.bash_session.execute(action)
                logger.info('Command execution completed, processing results')
                logger.debug(session.bash_session)
                logger.debug(observation)

                # 处理结果
                status = map_openhands_status(observation)

                # 提取输出
                output = getattr(observation, 'content', '')

                # 清理输出
                clean_output = strip_ansi_codes(output)

                return status, clean_output, observation.exit_code

            except Exception as e:
                logger.error(
                    f'Command execution error in sync mode: {e}', exc_info=True
                )
                return BashCommandStatus.TERMINATED, f'Command failed: {str(e)}', -1

        # 在线程池中执行命令
        status, clean_output, exit_code = await loop.run_in_executor(None, _run_command)

        # 更新会话状态
        session.status = status

        # 添加到会话缓冲区
        await session.add_output(clean_output)

        # 创建控制台记录
        console_record = ConsoleRecord(
            ps1='$ ',  # 简化处理
            command=visible_command,
            output=clean_output,
        )
        session.console_records.append(console_record)

        return ShellCommandResult(
            session_id=session.id,
            command=visible_command,
            status=status,
            output=clean_output,
            exit_code=exit_code,
            console=[console_record],
        )

    async def _execute_command_async(
        self,
        session: OpenHandsShellSession,
        command: str,
        timeout: int,
        display_command: Optional[str] = None,
    ):
        """异步执行命令（后台执行）"""
        from vendors.openhands.events.action.commands import CmdRunAction

        visible_command = display_command or command

        logger.info(
            f'Starting async command execution: {command} in session {session.id}'
        )

        try:
            # 检查会话是否还在管理器中
            logger.info(
                f'Checking session {session.id} in manager. Total sessions: {len(self.sessions)}'
            )
            if session.id not in self.sessions:
                logger.error(
                    f'Session {session.id} not found in manager at start of async execution'
                )
                return

            logger.info(
                f'Session {session.id} found, proceeding with command execution'
            )

            # 在线程池中执行OpenHands命令，避免阻塞
            loop = asyncio.get_event_loop()

            def _run_command():
                """在线程池中同步执行命令"""
                try:
                    logger.info(f'Thread execution starting for session {session.id}')
                    # 创建 OpenHands CmdRunAction
                    action = CmdRunAction(command=command)

                    # 执行命令
                    logger.info(f'Executing command via bash_session: {command}')
                    observation = session.bash_session.execute(action)
                    logger.info('Command execution completed, processing results')
                    logger.info(session.bash_session)
                    logger.info(observation)

                    # 处理结果
                    status = map_openhands_status(observation)

                    # 提取输出
                    output = getattr(observation, 'content', '')
                    # if hasattr(observation, 'error') and observation.error:
                    #     output += f"\nError: {observation.error}"

                    # 清理输出
                    clean_output = strip_ansi_codes(output)

                    logger.info(
                        f'Command execution results: status={status}, output={repr(clean_output)}'
                    )
                    return status, clean_output, observation.exit_code

                except Exception as e:
                    logger.error(
                        f'Command execution error in thread: {e}', exc_info=True
                    )
                    return BashCommandStatus.TERMINATED, f'Command failed: {str(e)}', -1

            # 在线程池中执行命令
            logger.info(f'Submitting command to thread pool for session {session.id}')
            status, output, exit_code = await loop.run_in_executor(None, _run_command)
            logger.info(f'Thread pool execution completed for session {session.id}')

            # 检查会话是否还在管理器中
            logger.info(
                f'Checking session {session.id} after thread execution. Total sessions: {len(self.sessions)}'
            )
            if session.id not in self.sessions:
                logger.error(
                    f'Session {session.id} disappeared after thread execution!'
                )
                return

            # 更新会话状态
            logger.info(f'Updating session {session.id} status to {status}')
            session.status = status
            session.exit_code = exit_code

            # 添加输出到缓冲区（这会通知订阅者）
            await session.add_output(output)

            # 创建控制台记录
            console_record = ConsoleRecord(
                ps1='$ ',
                command=visible_command,
                output=output,
            )
            session.console_records.append(console_record)

            logger.info(f'Async command completed: {session.id}, status: {status}')

        except asyncio.CancelledError:
            logger.warning(f'Async execution was cancelled for session {session.id}')
            # Don't set status or add output for cancelled tasks
            raise
        except Exception as e:
            logger.error(
                f'Exception in async execution for session {session.id}: {e}',
                exc_info=True,
            )
            # Check if session still exists before updating it
            if session.id in self.sessions:
                session.status = BashCommandStatus.TERMINATED
                error_msg = f'Command failed: {str(e)}'
                await session.add_output(error_msg)
            logger.error(f'Async command failed: {e}')

    async def view_session(self, session_id: str, limit: int = 1000) -> ShellViewResult:
        """查看会话输出"""

        session = self.get_session(session_id)
        if not session:
            raise ValueError(f'Session {session_id} not found')

        async with session._lock:
            # 获取最近的输出
            recent_output = (
                session.output_buffer[-limit:] if session.output_buffer else []
            )
            output = ''.join(recent_output)

        return ShellViewResult(
            output=output,
            session_id=session_id,
            console=session.console_records,
            status=session.status,
            command=session.current_command,
            exit_code=session.exit_code,
        )

    async def subscribe_char(
        self, session_id: str, subscriber_id: str
    ) -> Optional[asyncio.Queue]:
        """订阅字符输出"""

        session = self.get_session(session_id)
        if not session:
            return None

        return await session.subscribe_char(subscriber_id)

    async def unsubscribe_char(self, session_id: str, subscriber_id: str):
        """取消字符订阅"""

        session = self.get_session(session_id)
        if session:
            await session.unsubscribe_char(subscriber_id)

    async def delete_session(self, session_id: str) -> bool:
        """删除会话"""

        async with self._lock:
            session = self.sessions.get(session_id)
            if not session:
                return False

            # 关闭 OpenHands session
            if session.bash_session:
                try:
                    session.bash_session.close()
                except Exception as e:
                    logger.warning(f'Error closing bash session: {e}')

            # 清理订阅者
            session.char_subscribers.clear()
            session.line_subscribers.clear()

            # 从管理器中移除
            del self.sessions[session_id]
            session.active = False

            logger.info(f'Deleted session: {session_id}')
            return True

    def get_session(self, session_id: str) -> Optional[OpenHandsShellSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[OpenHandsShellSession]:
        """列出所有会话"""
        return list(self.sessions.values())

    def get_session_stats(self) -> ShellSessionStats:
        """获取会话统计信息"""
        current_time = time.time()
        active_count = 0
        idle_count = 0

        for session in self.sessions.values():
            last_used_timestamp = session.last_used_at.timestamp()
            if current_time - last_used_timestamp < 300:  # 5分钟内为活跃
                active_count += 1
            else:
                idle_count += 1

        return ShellSessionStats(
            total_sessions=len(self.sessions),
            active_sessions=active_count,
            idle_sessions=idle_count,
            max_sessions=self.max_sessions,
            session_timeout=self.session_timeout,
            usage_ratio=(
                len(self.sessions) / self.max_sessions if self.max_sessions > 0 else 0.0
            ),
        )

    async def cleanup_all_sessions(self):
        """清理所有会话（用于关闭或重启）"""
        session_ids = list(self.sessions.keys())
        for session_id in session_ids:
            await self._force_delete_session(session_id, reason='cleanup_all')
        logger.info(f'Cleaned up all {len(session_ids)} sessions')

    def get_active_sessions(self) -> ActiveShellSessionsResult:
        """Get info about active shell sessions"""
        # 清理过期会话 (如果有事件循环的话)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._cleanup_expired_sessions())
        except RuntimeError:
            # 没有运行的事件循环，跳过清理
            pass

        sessions = {}
        current_time = time.time()

        for session_id, session in self.sessions.items():
            sessions[session_id] = ShellSessionInfo(
                working_dir=session.working_dir,
                created_at=session.created_at,
                last_used_at=session.last_used_at,
                age_seconds=int(current_time - session.last_used_at.timestamp()),
                status=session.status.value,
                current_command=session.current_command,
            )

        return ActiveShellSessionsResult(sessions=sessions)

    def cleanup_session(self, session_id: str) -> bool:
        """Manually cleanup a specific shell session"""
        if session_id in self.sessions:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(
                    self._force_delete_session(session_id, reason='manual_cleanup')
                )
            except RuntimeError:
                pass
            return True
        return False
