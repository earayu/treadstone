from auth0.authentication.token_verifier import AsymmetricSignatureVerifier, TokenVerifier

from treadstone.config import settings


def get_jwt_token_verifier(jwks_url: str, issuer: str, client_id: str) -> TokenVerifier:
    sv = AsymmetricSignatureVerifier(jwks_url)
    return TokenVerifier(signature_verifier=sv, issuer=issuer, audience=client_id)


tv: TokenVerifier | None = None

match settings.auth_type:
    case "auth0":
        issuer = f"https://{settings.auth0_domain}/"
        jwks_url = f"https://{settings.auth0_domain}/.well-known/jwks.json"
        tv = get_jwt_token_verifier(jwks_url, issuer, settings.auth0_client_id)
    case "authing":
        issuer = f"https://{settings.authing_domain}/oidc"
        jwks_url = f"https://{settings.authing_domain}/oidc/.well-known/jwks.json"
        tv = get_jwt_token_verifier(jwks_url, issuer, settings.authing_app_id)
    case "logto":
        issuer = f"http://{settings.logto_domain}/oidc"
        jwks_url = f"http://{settings.logto_domain}/oidc/jwks"
        tv = get_jwt_token_verifier(jwks_url, issuer, settings.logto_app_id)
    case _:
        tv = None
