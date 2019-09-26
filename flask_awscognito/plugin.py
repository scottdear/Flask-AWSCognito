from functools import wraps

from flask import _app_ctx_stack, abort, request, make_response, jsonify
from flask_awscognito.utils import extract_access_token, get_state
from flask_awscognito.services import cognito_service_factory, token_service_factory
from flask_awscognito.exceptions import FlaskAWSCognitoError, TokenVerifyError
from flask_awscognito.constants import (CONTEXT_KEY_COGNITO_SERVICE,
                                        CONTEXT_KEY_TOKEN_SERVICE,
                                        CONFIG_KEY_POOL_CLIENT_ID,
                                        CONFIG_KEY_POOL_ID,
                                        CONFIG_KEY_REDIRECT_URL)


class AWSCognitoAuthentication:
    def __init__(self, app=None,
                 token_service_factory=token_service_factory,
                 cognito_service_factory=cognito_service_factory):
        self.app = app
        self.user_pool_id = None
        self.user_pool_client_id = None
        self.redirect_url = None
        self.claims = None
        self.token_service_factory = token_service_factory
        self.cognito_service_factory = cognito_service_factory
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        self.user_pool_id = app.config[CONFIG_KEY_POOL_ID]
        self.user_pool_client_id = app.config[CONFIG_KEY_POOL_CLIENT_ID]
        self.redirect_url = app.config[CONFIG_KEY_REDIRECT_URL]

    @property
    def token_service(self):
        ctx = _app_ctx_stack.top
        if ctx is not None:
            if not hasattr(ctx, CONTEXT_KEY_TOKEN_SERVICE):
                token_service = self.token_service_factory(self.user_pool_id, self.user_pool_client_id)
                setattr(ctx, CONTEXT_KEY_TOKEN_SERVICE, token_service)
            return getattr(ctx, CONTEXT_KEY_TOKEN_SERVICE)

    @property
    def cognito_service(self):
        ctx = _app_ctx_stack.top
        if ctx is not None:
            if not hasattr(ctx, CONTEXT_KEY_COGNITO_SERVICE):
                cognito_service = self.cognito_service_factory(self.user_pool_id,
                                                               self.user_pool_client_id,
                                                               self.redirect_url)
                setattr(ctx, CONTEXT_KEY_COGNITO_SERVICE, cognito_service)
            return getattr(ctx, CONTEXT_KEY_COGNITO_SERVICE)

    def get_sign_in_url(self):
        sign_in_url = self.cognito_service.get_sign_in_url()
        return sign_in_url

    def get_access_token(self, request_args):
        code = request_args.get('code')
        state = request_args.get('state')
        expected_state = get_state(self.user_pool_id, self.user_pool_client_id)
        if state != expected_state:
            raise FlaskAWSCognitoError('State for CSRF is not correct ')
        access_token = self.cognito_service.exchange_code_for_token(code)
        return access_token

    def authentication_required(self, view):
        @wraps(view)
        def decorated(*args, **kwargs):

            access_token = extract_access_token(request.headers)
            try:
                print(self.token_service.verify(access_token))
                self.claims = self.token_service.claims
            except TokenVerifyError as e:
                _ = request.data
                abort(make_response(jsonify(message=str(e)), 401))

            return view(*args, **kwargs)
        return decorated