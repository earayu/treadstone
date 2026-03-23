"""Auth commands — login, logout, register, whoami, change-password, invite, users, delete-user."""

from __future__ import annotations

import click

from treadstone.cli._client import build_client, require_auth
from treadstone.cli._output import handle_error, is_json_mode, print_detail, print_json, print_table


@click.group()
def auth() -> None:
    """Authentication and user management.

    Register, log in, manage users, and change passwords.

    \b
    Quick start:
      treadstone auth register          Create a new account
      treadstone auth login             Log in (saves session)
      treadstone auth whoami            Verify current identity
    """


@auth.command("login")
@click.option("--email", required=True, prompt=True, help="Account email.")
@click.option("--password", required=True, prompt=True, hide_input=True, help="Account password.")
@click.pass_context
def login(ctx: click.Context, email: str, password: str) -> None:
    """Log in with email and password.

    If --email or --password are not provided, you will be prompted interactively.
    """
    client = build_client(ctx)
    resp = client.post("/v1/auth/login", json={"email": email, "password": password})
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo("Login successful.")


@auth.command("logout")
@click.pass_context
def logout(ctx: click.Context) -> None:
    """Log out (clear session cookie)."""
    client = build_client(ctx)
    resp = client.post("/v1/auth/logout")
    handle_error(resp)
    if is_json_mode(ctx):
        print_json(resp.json())
    else:
        click.echo("Logged out.")


@auth.command("register")
@click.option("--email", required=True, prompt=True, help="Account email.")
@click.option("--password", required=True, prompt=True, hide_input=True, confirmation_prompt=True, help="Password.")
@click.option("--invitation-token", default=None, help="Invitation token (required in invitation mode).")
@click.pass_context
def register(ctx: click.Context, email: str, password: str, invitation_token: str | None) -> None:
    """Register a new account.

    In invitation-only mode, an --invitation-token is required.
    """
    client = build_client(ctx)
    body: dict = {"email": email, "password": password}
    if invitation_token:
        body["invitation_token"] = invitation_token
    resp = client.post("/v1/auth/register", json=body)
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Registered: {data['email']} (role: {data['role']})")


@auth.command("whoami")
@click.pass_context
def whoami(ctx: click.Context) -> None:
    """Show current user info."""
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
    """Change your password."""
    client = require_auth(ctx)
    resp = client.post("/v1/auth/change-password", json={"old_password": old_password, "new_password": new_password})
    handle_error(resp)
    if is_json_mode(ctx):
        print_json(resp.json())
    else:
        click.echo("Password changed.")


@auth.command("invite")
@click.option("--email", required=True, help="Email of the person to invite.")
@click.option("--role", default="ro", help="Role for the invitee (admin or ro).")
@click.pass_context
def invite(ctx: click.Context, email: str, role: str) -> None:
    """Generate an invitation token for a new user (admin only)."""
    client = require_auth(ctx)
    resp = client.post("/v1/auth/invite", json={"email": email, "role": role})
    handle_error(resp)
    data = resp.json()
    if is_json_mode(ctx):
        print_json(data)
    else:
        click.echo(f"Invitation sent to {data['email']}. Token: {data['token']}")


@auth.command("users")
@click.option("--limit", default=100, type=int, help="Max results.")
@click.option("--offset", default=0, type=int, help="Skip N results.")
@click.pass_context
def list_users(ctx: click.Context, limit: int, offset: int) -> None:
    """List all registered users (admin only)."""
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
    """Delete a user (admin only)."""
    client = require_auth(ctx)
    resp = client.delete(f"/v1/auth/users/{user_id}")
    handle_error(resp)
    click.echo(f"User {user_id} deleted.")
