"""Auth commands — login, logout, register, whoami, change-password, users, delete-user."""

from __future__ import annotations

import click
import httpx

from treadstone_cli._client import (
    build_client,
    build_session_client,
    clear_session,
    get_base_url,
    get_session_token,
    require_auth,
    save_session,
)
from treadstone_cli._output import handle_error, is_json_mode, print_detail, print_json, print_table


@click.group()
def auth() -> None:
    """Authentication and user management.

    Register, log in, manage users, and change passwords. Successful logins
    save a local control-plane session for the active base URL.

    \b
    Quick start:
      treadstone auth register                        Create a new account
      treadstone auth login                           Save a local session
      treadstone auth whoami                          Verify current identity
      treadstone api-keys create --name agent --save Create a reusable API key
    """


@auth.command("login")
@click.option("--email", required=True, prompt=True, help="Account email.")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Account password.")
@click.pass_context
def login(ctx: click.Context, email: str, password: str) -> None:
    """Log in with email and password.

    If --email or --password are not provided, you will be prompted
    interactively. On success, the CLI stores the returned session cookie and
    reuses it for future control-plane commands until you run logout.
    """
    client = build_client(ctx)
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    handle_error(resp)
    data = resp.json()
    session_token = resp.cookies.get("session")
    if not session_token:
        raise click.ClickException("Login succeeded but no session cookie was returned.")
    base_url = get_base_url(ctx)
    save_session(base_url, session_token)
    if is_json_mode(ctx):
        print_json({**data, "base_url": base_url, "session_saved": True})
    else:
        click.echo(f"Login successful. Saved session for {base_url}.")


@auth.command("logout")
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Log out and clear the saved local session for the active base URL."""
    base_url = get_base_url(ctx)
    session_token = get_session_token(ctx)
    if session_token:
        client = build_session_client(base_url, session_token)
        try:
            resp = client.post("/v1/auth/logout")
            handle_error(resp)
            data = resp.json()
        except httpx.HTTPError:
            data = {"detail": "Logout successful"}
    else:
        data = {"detail": "Logout successful"}
    session_cleared = clear_session(base_url)
    if is_json_mode(ctx):
        print_json({**data, "base_url": base_url, "session_cleared": session_cleared})
    else:
        if session_cleared:
            click.echo(f"Logged out. Cleared saved session for {base_url}.")
        else:
            click.echo(f"No saved session for {base_url}.")


@auth.command("register")
@click.option("--email", required=True, prompt=True, help="Account email.")
@click.option("--password", required=True, prompt=True, hide_input=True, confirmation_prompt=True, help="Password.")
@click.pass_context
def register(ctx: click.Context, email: str, password: str) -> None:
    """Register a new account."""
    client = build_client(ctx)
    resp = client.post("/v1/auth/register", json={"email": email, "password": password})
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Registered: {data['email']} (role: {data['role']})")


@auth.command("whoami")
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show the current user resolved from the active API key or saved session."""
    client = require_auth(ctx)
    resp = client.get("/v1/auth/user")
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        print_detail(data, title="Current User")


@auth.command("change-password")
@click.option("--old-password", required=True, prompt=True, hide_input=True, help="Current password.")
@click.option(
    "--new-password", required=True, prompt=True, hide_input=True, confirmation_prompt=True, help="New password."
)
@click.pass_context
def change_password(ctx: click.Context, old_password: str, new_password: str) -> None:
    """Change your password for the current account."""
    client = require_auth(ctx)
    resp = client.post("/v1/auth/change-password", json={"old_password": old_password, "new_password": new_password})
    handle_error(resp)
    if is_json_mode(ctx):
        print_json(resp.json())
    else:
        click.echo("Password changed.")


@auth.command("users")
@click.option("--limit", default=100, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Skip N results.")
@click.pass_context
def list_users(ctx: click.Context, limit: int, offset: int) -> None:
    """List users visible to the current account.

    Admin accounts can see all users. Non-admin accounts only see themselves.
    """
    client = require_auth(ctx)
    resp = client.get("/v1/auth/users", params={"limit": limit, "offset": offset})
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        items = data.get("items", [])
        rows = [[u["id"], u["email"], u["role"]] for u in items]
        print_table(["ID", "Email", "Role"], rows, title=f"Users ({data['total']} total)")


@auth.command("delete-user")
@click.argument("user_id")
@click.pass_context
def delete_user(ctx: click.Context, user_id: str) -> None:
    """Delete a user by user ID (admin only)."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/auth/users/{user_id}")
    handle_error(resp)
    click.echo(f"User {user_id} deleted.")
