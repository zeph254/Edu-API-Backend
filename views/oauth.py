from authlib.integrations.flask_client import OAuth
from flask import current_app, url_for, jsonify
from models import db, User
from datetime import datetime
import os

oauth = OAuth(current_app)

def init_oauth(app):
    """Initialize OAuth providers"""
    google = oauth.register(
        name='google',
        client_id=os.getenv('GOOGLE_CLIENT_ID'),
        client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
        access_token_url='https://accounts.google.com/o/oauth2/token',
        authorize_url='https://accounts.google.com/o/oauth2/auth',
        api_base_url='https://www.googleapis.com/oauth2/v1/',
        client_kwargs={'scope': 'openid email profile'},
    )
    
    # Add other providers (Microsoft, Facebook, etc.) here
    return oauth

def handle_oauth_callback(provider_name):
    """Handle OAuth callback for any provider"""
    try:
        provider = oauth.create_client(provider_name)
        token = provider.authorize_access_token()
        user_info = provider.get('userinfo').json()
    except Exception as e:
        current_app.logger.error(f"OAuth error: {str(e)}")
        return None, "Authentication failed"
    
    email = user_info.get('email')
    if not email:
        return None, "Email not provided by provider"
    
    # Find or create user
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            is_email_verified=True,
            is_active=True,
            created_at=datetime.utcnow()
        )
        db.session.add(user)
        db.session.commit()
    
    return user, None

def get_oauth_provider(provider_name):
    """Get OAuth provider configuration"""
    return oauth.create_client(provider_name)