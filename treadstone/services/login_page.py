"""Shared HTML login page renderer for browser and CLI login flows."""

from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from fastapi.responses import HTMLResponse

from treadstone.core.users import get_github_oauth_client, get_google_oauth_client


def render_login_page(
    *,
    title: str,
    subtitle: str,
    form_action: str,
    hidden_fields: dict[str, str],
    google_authorize_params: dict[str, str] | None = None,
    github_authorize_params: dict[str, str] | None = None,
    error: str | None = None,
    status_code: int = 200,
) -> HTMLResponse:
    error_html = ""
    if error:
        error_html = f'<p style="color:#b91c1c;margin-bottom:16px;">{escape(error)}</p>'

    oauth_buttons: list[str] = []
    if get_google_oauth_client() and google_authorize_params is not None:
        google_href = f"/v1/auth/google/authorize?{urlencode(google_authorize_params)}"
        oauth_buttons.append(
            '<a href="'
            f"{escape(google_href, quote=True)}"
            '" style="display:block;text-align:center;margin-bottom:12px;padding:10px 12px;'
            'border:1px solid #d4d4d8;border-radius:8px;color:#111827;font-weight:600;text-decoration:none;">'
            "Continue with Google"
            "</a>"
        )
    if get_github_oauth_client() and github_authorize_params is not None:
        github_href = f"/v1/auth/github/authorize?{urlencode(github_authorize_params)}"
        oauth_buttons.append(
            '<a href="'
            f"{escape(github_href, quote=True)}"
            '" style="display:block;text-align:center;margin-bottom:12px;padding:10px 12px;'
            'border:1px solid #d4d4d8;border-radius:8px;color:#111827;font-weight:600;text-decoration:none;">'
            "Continue with GitHub"
            "</a>"
        )

    oauth_html = "".join(oauth_buttons)
    divider_html = ""
    if oauth_buttons:
        divider_html = (
            '<p style="margin:20px 0;color:#71717a;text-align:center;font-size:14px;">or continue with email</p>'
        )

    hidden_inputs = "".join(
        f'<input type="hidden" name="{escape(k, quote=True)}" value="{escape(v, quote=True)}">'
        for k, v in hidden_fields.items()
    )

    body_style = (
        "font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;padding:40px;"
    )
    main_style = (
        "max-width:420px;margin:0 auto;background:white;padding:24px;"
        "border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.08);"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Treadstone Login</title>
</head>
<body style="{body_style}">
  <main style="{main_style}">
    <h1 style="font-size:24px;margin-bottom:12px;">{escape(title)}</h1>
    <p style="color:#555;margin-bottom:20px;">{escape(subtitle)}</p>
    {error_html}
    {oauth_html}
    {divider_html}
    <form method="post" action="{escape(form_action, quote=True)}">
      {hidden_inputs}
      <label style="display:block;margin-bottom:12px;">
        <span style="display:block;margin-bottom:6px;">Email</span>
        <input
          type="email"
          name="email"
          required
          style="width:100%;padding:10px 12px;border:1px solid #d4d4d8;border-radius:8px;"
        >
      </label>
      <label style="display:block;margin-bottom:20px;">
        <span style="display:block;margin-bottom:6px;">Password</span>
        <input
          type="password"
          name="password"
          required
          style="width:100%;padding:10px 12px;border:1px solid #d4d4d8;border-radius:8px;"
        >
      </label>
      <button
        type="submit"
        style="width:100%;padding:10px 12px;border:0;border-radius:8px;background:#111827;color:white;font-weight:600;"
      >
        Sign in
      </button>
    </form>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html, status_code=status_code)


def render_success_page(
    message: str = "Login successful. You can close this window and return to your terminal.",
) -> HTMLResponse:
    body_style = (
        "font-family:system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#f5f5f5;padding:40px;"
    )
    main_style = (
        "max-width:420px;margin:0 auto;background:white;padding:24px;"
        "border-radius:12px;box-shadow:0 10px 30px rgba(0,0,0,0.08);"
    )
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Login Successful</title>
</head>
<body style="{body_style}">
  <main style="{main_style}">
    <h1 style="font-size:24px;margin-bottom:12px;">Login successful</h1>
    <p style="color:#555;">{escape(message)}</p>
  </main>
</body>
</html>"""
    return HTMLResponse(content=html)
