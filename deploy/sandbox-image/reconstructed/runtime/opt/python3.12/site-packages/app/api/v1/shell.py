import asyncio
import json
import logging
import time
from typing import Optional

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse

from app.core.service_container import services
from app.models.shell import (
    ActiveShellSessionsResult,
    BashCommandStatus,
    ShellCommandResult,
    ShellKillResult,
    ShellViewResult,
    ShellWaitResult,
    ShellWriteResult,
)
from app.schemas.response import Response
from app.schemas.shell import (
    ShellCreateSessionRequest,
    ShellCreateSessionResponse,
    ShellExecRequest,
    ShellKillProcessRequest,
    ShellViewRequest,
    ShellWaitRequest,
    ShellWriteToProcessRequest,
)
from app.services.shell import OpenHandsShellManager
from app.utils import normalize_cwd


router = APIRouter()
logger = logging.getLogger(__name__)


async def _wait_for_command_completion(session_id: str):
    """等待命令完成（通过检查会话状态）"""
    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
    session = terminal_manager.get_session(session_id)
    if not session or not session.active:
        return

    max_wait_time = 120  # 最大等待120秒
    poll_interval = 0.1  # 每100ms检查一次状态
    waited_time = 0

    while waited_time < max_wait_time:
        if session.status != BashCommandStatus.RUNNING:
            break
        await asyncio.sleep(poll_interval)
        waited_time += poll_interval


async def receive_input(websocket: WebSocket, session):
    """接收 WebSocket 输入并发送到终端（使用 terminado）"""
    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                # 尝试解析 JSON 消息
                message = json.loads(raw_data)
                if message.get('type') == 'input':
                    session.send_input(message.get('data', ''))
                elif message.get('type') == 'resize':
                    cols = message.get('data', {}).get('cols', 80)
                    rows = message.get('data', {}).get('rows', 24)
                    try:
                        session.resize(rows, cols)
                    except Exception as e:
                        logger.warning(f'Failed to resize terminal: {e}')
                elif message.get('type') == 'ping':
                    # 响应心跳ping消息
                    pong_message = {
                        'type': 'pong',
                        'timestamp': message.get('timestamp', int(time.time() * 1000)),
                    }
                    await websocket.send_text(json.dumps(pong_message))
            except json.JSONDecodeError:
                # 如果不是 JSON，直接作为输入发送（向后兼容）
                session.send_input(raw_data)
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f'Error receiving input: {e}')
        raise


async def send_output(websocket: WebSocket, queue: asyncio.Queue):
    """从队列读取输出并发送到 WebSocket"""
    try:
        while True:
            output = await queue.get()
            # 发送标准格式的消息给 xterm.js
            message = {'type': 'output', 'data': output}
            await websocket.send_text(json.dumps(message))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f'Error sending output: {e}')
        raise


async def send_heartbeat(websocket: WebSocket):
    """定期发送心跳ping消息以保持连接活跃"""
    try:
        while True:
            # 每30秒发送一次心跳
            await asyncio.sleep(30)
            ping_message = {'type': 'ping', 'timestamp': int(time.time() * 1000)}
            await websocket.send_text(json.dumps(ping_message))
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f'Error sending heartbeat: {e}')
        raise


@router.post(
    '/exec',
    response_model=Response[ShellCommandResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'exec_command',
    },
)
async def exec_command(request: ShellExecRequest, http_request: Request):
    """
    Execute command in the specified shell session
    Supports SSE streaming if Accept header contains 'text/event-stream'
    """
    # If no session ID is provided, automatically create one

    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')

    accept = http_request.headers.get('accept', '')
    working_dir = normalize_cwd(request.exec_dir)

    logger.info(f'exec_command request: {request}')

    if not request.id:
        session = await terminal_manager.create_session(working_dir=working_dir)
        session_id = session.id
    else:
        session_id = request.id
        session = terminal_manager.get_session(session_id)
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')

    """
    FIXME: sse output bug: output will stuck sse pipeline finished
    """
    # 支持 SSE 流式输出
    if accept and 'text/event-stream' in accept:

        async def generate():
            # 创建订阅
            queue = await terminal_manager.subscribe_char(
                session_id, f'sse_{session_id}'
            )
            if not queue:
                yield f'data: {json.dumps({"error": "Failed to subscribe"})}\n\n'
                return

            try:
                # 异步执行命令
                await terminal_manager.execute_command(
                    session_id, request.command, async_mode=True
                )

                # 流式输出
                while True:
                    try:
                        output = await asyncio.wait_for(queue.get(), timeout=30)
                        yield f'data: {json.dumps({"output": output})}\n\n'
                    except asyncio.TimeoutError:
                        break

            finally:
                await terminal_manager.unsubscribe_char(session_id, f'sse_{session_id}')

        return StreamingResponse(generate(), media_type='text/event-stream')
    else:
        # 同步执行
        command_timeout = (
            request.timeout if request.timeout and request.timeout > 0 else None
        )

        if request.async_mode:
            # 异步模式：立即返回
            exec_kwargs = {'async_mode': True}
            if command_timeout:
                exec_kwargs['timeout'] = command_timeout
            result = await terminal_manager.execute_command(
                session_id, request.command, working_dir=working_dir, **exec_kwargs
            )
            return Response(
                success=True,
                message='Command sent for execution',
                data=result.model_dump(),
            )
        else:
            # 同步模式：等待输出
            exec_kwargs = {'async_mode': False}
            if command_timeout:
                exec_kwargs['timeout'] = command_timeout

            command_coro = terminal_manager.execute_command(
                session_id, request.command, working_dir=working_dir, **exec_kwargs
            )

            if command_timeout:
                command_task = asyncio.create_task(command_coro)
                try:
                    result = await asyncio.wait_for(
                        asyncio.shield(command_task), timeout=command_timeout
                    )
                    return Response(
                        success=True,
                        message='Command executed',
                        data=result.model_dump(),
                    )
                except asyncio.TimeoutError:

                    def _command_done_callback(task: asyncio.Task):
                        if task.cancelled():
                            logger.info(
                                f'Command task cancelled after timeout for session {session_id}'
                            )
                            return
                        exc = task.exception()
                        if exc:
                            logger.error(
                                f'Command task failed after timeout for session {session_id}: {exc}'
                            )

                    command_task.add_done_callback(_command_done_callback)

                running_result = ShellCommandResult(
                    session_id=session_id,
                    command=request.command,
                    status=BashCommandStatus.RUNNING,
                    output=None,
                    console=None,
                    exit_code=None,
                )
                timeout_message = (
                    f'Command still running (timeout {command_timeout:g}s reached)'
                )
                return Response(
                    success=True,
                    message=timeout_message,
                    data=running_result.model_dump(),
                )

            result = await command_coro
            return Response(
                success=True, message='Command executed', data=result.model_dump()
            )


@router.post(
    '/view',
    response_model=Response[ShellViewResult],
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'view',
    },
)
async def view_shell(request: ShellViewRequest, http_request: Request):
    """
    View output of the specified shell session
    Supports SSE streaming if Accept header contains 'text/event-stream'
    """

    accept = http_request.headers.get('accept', '')
    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')

    """
    FIXME: sse output bug: output will stuck sse pipeline finished
    """
    if accept and 'text/event-stream' in accept:
        # 检查会话是否存在（仅用于SSE模式）
        session = terminal_manager.get_session(request.id)
        if not session:
            raise HTTPException(status_code=404, detail='Session not found')

        # SSE 流式输出
        async def generate():
            queue = await terminal_manager.subscribe_char(
                request.id, f'view_{request.id}'
            )
            if not queue:
                yield f'data: {json.dumps({"error": "Failed to subscribe"})}\n\n'
                return

            try:
                timeout_count = 0
                max_timeouts = 3  # 最多3次超时后退出
                while timeout_count < max_timeouts:
                    try:
                        output = await asyncio.wait_for(
                            queue.get(), timeout=5
                        )  # 减少超时时间到5秒
                        yield f'data: {json.dumps({"output": output})}\n\n'
                        timeout_count = 0  # 重置超时计数
                    except asyncio.TimeoutError:
                        timeout_count += 1
                        if timeout_count < max_timeouts:
                            yield f'data: {json.dumps({"keepalive": True})}\n\n'
                        else:
                            # 达到最大超时次数，发送结束信号
                            yield f'data: {json.dumps({"end": True, "message": "No more output"})}\n\n'
                            break

            finally:
                await terminal_manager.unsubscribe_char(
                    request.id, f'view_{request.id}'
                )

        return StreamingResponse(generate(), media_type='text/event-stream')
    else:
        # 使用 TerminalManager 的 view_session 方法
        try:
            view_result = await terminal_manager.view_session(request.id)
            return Response(
                success=True, message='Session output', data=view_result.model_dump()
            )
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))


@router.post(
    '/wait',
    response_model=Response[ShellWaitResult],
    operation_id='wait_for_process',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'wait_for_process',
    },
)
async def wait_for_process(request: ShellWaitRequest):
    """
    Wait for the process in the specified shell session to return
    """
    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
    session = terminal_manager.get_session(request.id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    timeout = request.seconds or 30

    def _current_status() -> Optional[BashCommandStatus]:
        current_session = terminal_manager.get_session(request.id)
        if not current_session:
            return None
        return current_session.status

    def _build_wait_response(
        status: BashCommandStatus, wait_result: ShellWaitResult
    ) -> Response[ShellWaitResult]:
        if status == BashCommandStatus.COMPLETED:
            return Response(
                success=True,
                message='Process completed successfully',
                data=wait_result.model_dump(),
            )
        if status == BashCommandStatus.RUNNING:
            return Response(
                success=True,
                message='Process is still running',
                data=wait_result.model_dump(),
            )
        if status == BashCommandStatus.NO_CHANGE_TIMEOUT:
            return Response(
                success=True,
                message='Process is still running (no new output yet)',
                data=wait_result.model_dump(),
            )
        return Response(
            success=False,
            message=f'Process ended abnormally with status: {status.value}',
            data=wait_result.model_dump(),
        )

    try:
        # 等待命令完成或超时
        await asyncio.wait_for(
            asyncio.create_task(_wait_for_command_completion(request.id)),
            timeout=timeout,
        )

        status = _current_status()
        if status is None:
            # Session lost/unavailable - this is an error
            wait_result = ShellWaitResult(status=BashCommandStatus.TERMINATED)
            return Response(
                success=False,
                message='Session unavailable',
                data=wait_result.model_dump(),
            )

        wait_result = ShellWaitResult(status=status)
        return _build_wait_response(status, wait_result)
    except asyncio.TimeoutError:
        status = _current_status() or BashCommandStatus.RUNNING
        wait_result = ShellWaitResult(status=status)

        # Wait timeout - check if process is in normal or abnormal state
        if status in [
            BashCommandStatus.RUNNING,
            BashCommandStatus.COMPLETED,
            BashCommandStatus.NO_CHANGE_TIMEOUT,
        ]:
            return _build_wait_response(status, wait_result)
        else:
            # Abnormal states (TERMINATED, HARD_TIMEOUT)
            return Response(
                success=False,
                message=f'Process ended abnormally with status: {status.value}',
                data=wait_result.model_dump(),
            )


@router.post(
    '/write',
    response_model=Response[ShellWriteResult],
    operation_id='write_to_process',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'write_to_process',
    },
)
async def write_to_process(request: ShellWriteToProcessRequest):
    """
    Write input to the process in the specified shell session
    """
    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
    session = terminal_manager.get_session(request.id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    if not session.active:
        raise HTTPException(status_code=400, detail='Session is not active')

    try:
        # OpenHands 基于命令执行，将输入作为命令执行
        command = request.input

        # 异步执行命令
        await terminal_manager.execute_command(request.id, command, async_mode=True)

        write_result = ShellWriteResult(status=BashCommandStatus.RUNNING)
        return Response(
            success=True,
            message='Input executed successfully',
            data=write_result.model_dump(),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    '/kill',
    response_model=Response[ShellKillResult],
    operation_id='kill_shell_process',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'kill_process',
    },
)
async def kill_process(request: ShellKillProcessRequest):
    """
    Terminate the process in the specified shell session
    """
    terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
    session = terminal_manager.get_session(request.id)
    if not session:
        raise HTTPException(status_code=404, detail='Session not found')

    success = await terminal_manager.delete_session(request.id)
    if not success:
        raise HTTPException(status_code=500, detail='Kill session failed')

    kill_result = ShellKillResult(status=BashCommandStatus.TERMINATED, returncode=0)
    return Response(
        success=True, message='Process terminated', data=kill_result.model_dump()
    )


@router.post(
    '/sessions/create',
    response_model=Response[ShellCreateSessionResponse],
    operation_id='create_shell_session',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'create_session',
    },
)
async def create_session(request: ShellCreateSessionRequest):
    """
    Create a new shell session and return its ID
    If id already exists, return the existing session
    """
    try:
        terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
        working_dir = normalize_cwd(request.exec_dir) if request.exec_dir else None

        # Check if session already exists
        existing_session = terminal_manager.get_session(request.id)
        if existing_session:
            result = ShellCreateSessionResponse(
                session_id=existing_session.id, working_dir=existing_session.working_dir
            )
            return Response(
                success=True,
                message='Session had created successfully',
                data=result.model_dump(),
            )

        # Create new session with the provided/generated id
        session = await terminal_manager.create_session(
            session_id=request.id, working_dir=working_dir
        )

        result = ShellCreateSessionResponse(
            session_id=session.id, working_dir=session.working_dir
        )

        return Response(
            success=True,
            message='Session created successfully',
            data=result.model_dump(),
        )

    except Exception as e:
        logger.error(f'Error creating session: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create session: {str(e)}'
        )


@router.get(
    '/terminal-url',
    response_model=Response[str],
    operation_id='get_terminal_url',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'get_terminal_url',
    },
)
async def get_terminal_url(http_request: Request):
    """
    Create a new shell session and return the terminal URL
    """
    try:
        from app.utils import normalize_path_prefix

        terminal_ws_manager = services.get('terminal_ws_manager')

        # Create a new session
        session = await terminal_ws_manager.create_session()

        # Get the host from the request
        host = http_request.headers.get('host', http_request.url.netloc)

        # Check X-Forwarded-Proto first, fallback to request.url.scheme
        # In reverse proxy scenarios, the internal request may be http
        # but the external client connection is https
        forwarded_proto = http_request.headers.get('x-forwarded-proto', '').lower()
        if forwarded_proto in ('https', 'http'):
            is_https = forwarded_proto == 'https'
        else:
            is_https = http_request.url.scheme == 'https'

        http_scheme = 'https' if is_https else 'http'

        logger.info('Protocol detection - X-Forwarded-Proto: %s, request.url.scheme: %s, final: %s',
                   forwarded_proto or 'none', http_request.url.scheme, http_scheme)

        # Get and normalize path prefix from X-Forwarded-Prefix header
        path_prefix = normalize_path_prefix(
            http_request.headers.get('x-forwarded-prefix')
        )

        # Construct the terminal URL
        terminal_url = f'{http_scheme}://{host}{path_prefix}/terminal?session_id={session.id}'

        return Response(
            success=True, message='Terminal URL created successfully', data=terminal_url
        )

    except Exception as e:
        logger.error(f'Error creating terminal URL: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to create terminal URL: {str(e)}'
        )


@router.get(
    '/sessions',
    response_model=Response[ActiveShellSessionsResult],
    operation_id='list_shell_sessions',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'list_sessions',
    },
)
async def list_sessions():
    """
    List all active shell sessions
    """
    try:
        terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
        sessions = terminal_manager.get_active_sessions()

        return Response(
            success=True,
            message=f'Found {len(sessions.sessions)} active sessions',
            data=sessions.model_dump(),
        )

    except Exception as e:
        logger.error(f'Error listing sessions: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to list sessions: {str(e)}'
        )


@router.delete(
    '/sessions/{session_id}',
    response_model=Response,
    operation_id='cleanup_shell_session',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'cleanup_session',
    },
)
async def cleanup_session(session_id: str):
    """
    Manually cleanup a specific shell session
    """
    try:
        terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
        success = terminal_manager.cleanup_session(session_id)

        if success:
            return Response(
                success=True,
                message=f'Session {session_id} cleaned up successfully',
                data={'session_id': session_id},
            )
        else:
            return Response(
                success=False,
                message=f'Session {session_id} not found',
                data={'session_id': session_id},
            )

    except Exception as e:
        logger.error(f'Error cleaning up session {session_id}: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to cleanup session: {str(e)}'
        )


@router.delete(
    '/sessions',
    response_model=Response,
    operation_id='cleanup_all_sessions',
    openapi_extra={
        'x-fern-sdk-group-name': 'shell',
        'x-fern-sdk-method-name': 'cleanup_all_sessions',
    },
)
async def cleanup_all_sessions():
    """
    Cleanup all active shell sessions
    """
    try:
        terminal_manager: OpenHandsShellManager = services.get('terminal_manager')
        sessions_before = len(terminal_manager.get_active_sessions().sessions)
        await terminal_manager.cleanup_all_sessions()

        return Response(
            success=True,
            message=f'Cleaned up {sessions_before} sessions',
            data={'cleaned_sessions': sessions_before},
        )

    except Exception as e:
        logger.error(f'Error cleaning up all sessions: {e}')
        raise HTTPException(
            status_code=500, detail=f'Failed to cleanup sessions: {str(e)}'
        )


@router.websocket('/ws')
async def websocket_shell_endpoint(
    websocket: WebSocket, session_id: Optional[str] = Query(None)
):
    terminal_ws_manager = services.get('terminal_ws_manager')
    """
    WebSocket endpoint for interactive shell terminal
    """
    await websocket.accept()

    # 如果没有 session_id，创建新会话
    is_new_session = False
    if not session_id:
        session = await terminal_ws_manager.create_session()
        session_id = session.id
        is_new_session = True
        # 只有新会话才发送 session_id 消息
        message = {'type': 'session_id', 'data': session_id}
        await websocket.send_text(json.dumps(message))
    else:
        # 连接到现有会话
        session = terminal_ws_manager.get_session(session_id)
        if not session:
            error_message = {'type': 'error', 'data': 'Session not found'}
            await websocket.send_text(json.dumps(error_message))
            await websocket.close()
            return

    if not session.active:
        error_message = {'type': 'error', 'data': 'Session is not active'}
        await websocket.send_text(json.dumps(error_message))
        await websocket.close()
        return

    logger.info(f'WebSocket connected for session {session_id}')

    # 订阅字符输出
    subscriber_id = f'ws_{session_id}_{id(websocket)}'
    queue = await terminal_ws_manager.subscribe_char(session_id, subscriber_id)

    if not queue:
        error_message = {
            'type': 'error',
            'data': 'Session already has an active WebSocket connection',
        }
        await websocket.send_text(json.dumps(error_message))
        await websocket.close()
        return

    # 如果是现有会话，恢复历史输出
    if not is_new_session:
        async with session._lock:
            # 发送历史输出
            if session.output_buffer:
                historical_output = ''.join(session.output_buffer)
                if historical_output.strip():
                    restore_message = {
                        'type': 'restore_output',
                        'data': historical_output,
                    }
                    await websocket.send_text(json.dumps(restore_message))

        # 发送会话恢复完成消息
        restored_message = {
            'type': 'terminal_restored',
            'data': f'Session {session_id[:8]} restored',
        }
        await websocket.send_text(json.dumps(restored_message))
    else:
        # 新会话发送就绪消息
        ready_message = {
            'type': 'ready',
            'data': f'Terminal ready - Session: {session_id[:8]}',
        }
        await websocket.send_text(json.dumps(ready_message))

        # 发送初始提示
        session.send_input('\n')
        await asyncio.sleep(0.2)

    try:
        # 启动心跳任务（在后台运行，不等待完成）
        heartbeat_task = asyncio.create_task(send_heartbeat(websocket))

        # 创建主要任务：接收输入和发送输出
        receive_task = asyncio.create_task(receive_input(websocket, session))
        send_task = asyncio.create_task(send_output(websocket, queue))

        # 等待主要任务中的任一个完成（不包括心跳任务）
        done, pending = await asyncio.wait(
            [receive_task, send_task], return_when=asyncio.FIRST_COMPLETED
        )

        # 取消未完成的主要任务
        for task in pending:
            task.cancel()

        # 取消心跳任务
        heartbeat_task.cancel()

        # 等待已完成的任务以确保异常被处理
        for task in done:
            try:
                task.result()
            except Exception:
                pass  # 异常会在其他地方处理

    except WebSocketDisconnect:
        logger.info(f'WebSocket disconnected for session {session_id}')
    except Exception as e:
        logger.error(f'WebSocket error for session {session_id}: {e}')
    finally:
        await terminal_ws_manager.unsubscribe_char(session_id, subscriber_id)
        # 只有在WebSocket仍然连接时才尝试关闭
        if websocket.client_state.name != 'DISCONNECTED':
            try:
                await websocket.close()
            except RuntimeError:
                # WebSocket已经关闭，忽略错误
                pass
