import asyncio
import logging
import os
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

import tornado.ioloop
from terminado.management import NamedTermManager, PtyWithClients

from app.models.shell import (
    ConsoleRecord,
)


logger = logging.getLogger(__name__)


class MaxTerminalsReached(Exception):
    """An error raised when we exceed the max number of terminals."""

    def __init__(self, max_terminals: int) -> None:
        """Initialize the error."""
        self.max_terminals = max_terminals

    def __str__(self) -> str:
        """The string representation of the error."""
        return 'Cannot create more than %d terminals' % self.max_terminals


class EnhancedNamedTermManager(NamedTermManager):
    def get_terminal(self, term_name: str, **kwargs) -> PtyWithClients:  # type:ignore[override]
        """Get or create a terminal by name."""
        assert term_name is not None

        if term_name in self.terminals:
            return self.terminals[term_name]

        if self.max_terminals and len(self.terminals) >= self.max_terminals:
            raise MaxTerminalsReached(self.max_terminals)

        # Create new terminal
        self.log.info('New terminal with specified name: %s', term_name)
        term = self.new_terminal(**kwargs)
        term.term_name = term_name
        self.terminals[term_name] = term
        self.start_reading(term)
        return term


class TerminadoClient:
    """Terminado client adapter implementing the client protocol"""

    def __init__(self, session_id: str, terminal_session: 'TerminalWsSession'):
        self.session_id = session_id
        self.terminal_session = terminal_session
        self.size = (24, 80)  # Default terminal size (rows, cols)

    def on_pty_read(self, text: str) -> None:
        """Handle output from terminado terminal - matches TermSocket protocol"""
        # terminado 传递的是字符串，直接处理
        if isinstance(text, bytes):
            text = text.decode('utf-8', errors='replace')
        asyncio.create_task(self.terminal_session._handle_terminado_output(text))

    def on_pty_died(self) -> None:
        """Handle terminal death - matches TermSocket protocol"""
        self.terminal_session.active = False
        logger.info(f'Terminal died for session {self.session_id}')


@dataclass
class TerminalWsSession:
    """终端会话数据类"""

    id: str
    shell: str = '/bin/bash'
    working_dir: str = os.environ.get('WORKSPACE')
    environment: Dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_used_at: datetime = field(default_factory=datetime.now)
    active: bool = True
    unique_ps1: str = ''

    # Terminado 相关
    terminado_terminal: Optional[Any] = None
    terminado_client: Optional[TerminadoClient] = None

    # 兼容性：保持原有订阅者接口
    line_subscribers: Dict[str, Callable] = field(default_factory=dict)
    char_subscriber: Optional[asyncio.Queue] = None
    char_subscriber_id: Optional[str] = None

    # 输出处理
    _line_buffer: str = field(default_factory=str)  # 字符流重组缓冲区

    # 输出缓冲（保持兼容）
    output_buffer: List[str] = field(default_factory=list)
    console_records: List[ConsoleRecord] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def _handle_terminado_output(self, text: str) -> None:
        """处理 terminado 输出，保持与原有接口兼容"""
        async with self._lock:
            # 添加到缓冲区
            self.output_buffer.append(text)

            # 通知字符订阅者
            if self.char_subscriber:
                try:
                    await self.char_subscriber.put(text)
                except asyncio.QueueFull:
                    logger.warning(f'Character queue full for session {self.id}')

            # 处理行级别的输出 - 重新设计以处理字符流
            # 将字符流重组为行，然后通知行订阅者
            if hasattr(self, '_line_buffer'):
                self._line_buffer += text
            else:
                self._line_buffer = text

            # 检查是否有完整的行（以 \n 或 \r 结尾）
            while '\n' in self._line_buffer or '\r' in self._line_buffer:
                # 找到行结束符
                if '\n' in self._line_buffer:
                    line, self._line_buffer = self._line_buffer.split('\n', 1)
                elif '\r' in self._line_buffer:
                    line, self._line_buffer = self._line_buffer.split('\r', 1)

                # 如果行有内容，通知订阅者
                if line.strip():
                    for subscriber_id, callback in self.line_subscribers.items():
                        try:
                            asyncio.create_task(callback(self.id, line))
                        except Exception as e:
                            logger.error(
                                f'Error calling subscriber {subscriber_id}: {e}'
                            )

    def send_input(self, text: str) -> None:
        """发送输入到终端"""
        if self.terminado_terminal and self.terminado_terminal.ptyproc:
            # ptyprocess.write() 接受字符串，不需要手动编码
            self.terminado_terminal.ptyproc.write(text)

    def resize(self, rows: int, cols: int) -> None:
        """调整终端大小"""
        if self.terminado_terminal and self.terminado_terminal.ptyproc:
            self.terminado_terminal.ptyproc.setwinsize(rows, cols)


class TerminalWsManager:
    """终端会话管理器（使用 terminado backend）"""

    def __init__(self):
        self.sessions: Dict[str, TerminalWsSession] = {}
        self._lock = asyncio.Lock()

        # 确保 Tornado IOLoop 运行
        self._ensure_tornado_ioloop()

        # 初始化 terminado 管理器
        self.terminado_manager = EnhancedNamedTermManager(
            shell_command=['/bin/bash', '-i'],
            extra_env={},
            term_settings={'cwd': os.environ.get('WORKSPACE')},
        )

    def _ensure_tornado_ioloop(self):
        """确保 Tornado IOLoop 在单独的线程中运行"""
        try:
            # 检查是否已有 IOLoop 运行
            loop = tornado.ioloop.IOLoop.current()
            if not loop.asyncio_loop.is_running():
                # 如果 IOLoop 未运行，在后台线程中启动
                self._start_tornado_thread()
        except RuntimeError:
            # 如果没有当前 IOLoop，创建并启动
            self._start_tornado_thread()

    def _start_tornado_thread(self):
        """在后台线程中启动 Tornado IOLoop"""

        def run_tornado():
            # 创建新的 IOLoop
            loop = tornado.ioloop.IOLoop()
            asyncio.set_event_loop(loop.asyncio_loop)
            # 运行 IOLoop（这会阻塞直到停止）
            loop.start()

        # 在守护线程中运行 Tornado
        tornado_thread = threading.Thread(target=run_tornado, daemon=True)
        tornado_thread.start()

        # 等待 IOLoop 启动
        import time

        time.sleep(0.1)

    async def create_session(
        self,
        session_id: Optional[str] = None,
        shell: str = '/bin/bash',
        working_dir: Optional[str] = None,
        shell_args: List[str] = None,
        environment: Dict[str, str] = None,
    ) -> TerminalWsSession:
        """创建新的终端会话（使用 terminado）"""

        if session_id is None:
            session_id = str(uuid.uuid4())

        if working_dir is None:
            working_dir = os.environ.get('WORKSPACE', '/tmp')

        if shell_args is None:
            shell_args = ['-i']

        if environment is None:
            environment = {}

        # 创建简洁的 PS1 提示符
        if 'bash' in shell:
            unique_ps1 = '\\u@\\h:\\w$ '
        elif 'zsh' in shell:
            unique_ps1 = '%n@%m:%~% '
        else:
            unique_ps1 = '$ '

        try:
            # 使用 terminado 创建终端 (get_terminal 已经调用了 start_reading)
            terminado_terminal = self.terminado_manager.get_terminal(
                session_id, cwd=working_dir
            )

            # 创建兼容性会话对象
            session = TerminalWsSession(
                id=session_id,
                shell=shell,
                working_dir=working_dir,
                environment=environment,
                unique_ps1=unique_ps1,
                terminado_terminal=terminado_terminal,
            )

            # 创建客户端适配器并注册到终端
            client = TerminadoClient(session_id, session)
            session.terminado_client = client

            # 将客户端注册到终端的客户端列表中（这是 terminado 的正确方式）
            terminado_terminal.clients.append(client)

            async with self._lock:
                self.sessions[session_id] = session

            # 初始化终端
            await asyncio.sleep(0.5)
            session.send_input(f"export PS1='{unique_ps1}'\n")
            session.send_input(f"export SESSION_ID='{session_id}'\n")
            session.send_input('clear\n')

            logger.info(f'Session {session_id} created successfully with terminado')
            return session

        except Exception as e:
            logger.error(f'Failed to create session: {e}')
            raise

    async def resize_pty(self, session_id: str, cols: int, rows: int):
        """调整终端大小（使用 terminado）"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f'Session {session_id} not found')

        try:
            if session.terminado_client:
                session.terminado_client.size = (rows, cols)
            if session.terminado_terminal:
                session.terminado_terminal.resize_to_smallest()
            logger.info(f'Resized session {session_id} to {cols}x{rows}')
            return True
        except Exception as e:
            logger.error(f'Failed to resize PTY: {e}')
            raise

    async def subscribe_char(
        self, session_id: str, subscriber_id: str
    ) -> Optional[asyncio.Queue]:
        """订阅字符输出"""
        session = self.sessions.get(session_id)
        if not session:
            return None

        async with session._lock:
            if session.char_subscriber:
                logger.warning(f'Session {session_id} already has char subscriber')
                return None

            session.char_subscriber = asyncio.Queue(maxsize=1000)
            session.char_subscriber_id = subscriber_id
            logger.info(
                f'Added char subscriber {subscriber_id} to session {session_id}'
            )
            return session.char_subscriber

    async def unsubscribe_char(self, session_id: str, subscriber_id: str):
        """取消字符订阅"""
        session = self.sessions.get(session_id)
        if not session:
            return

        async with session._lock:
            if session.char_subscriber_id == subscriber_id:
                session.char_subscriber = None
                session.char_subscriber_id = None
                logger.info(
                    f'Removed char subscriber {subscriber_id} from session {session_id}'
                )

    def get_session(self, session_id: str) -> Optional[TerminalWsSession]:
        """获取会话"""
        return self.sessions.get(session_id)

    def list_sessions(self) -> List[TerminalWsSession]:
        """列出所有会话"""
        return list(self.sessions.values())
