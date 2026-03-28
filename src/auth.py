"""Authentication module for JTVO Dashboard.

Provides multiple authentication methods:
1. Password authentication (simple)
2. Username + Password authentication
3. Google OAuth (via streamlit-authenticator)
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Optional

import streamlit as st


def _get_password_hash(password: str) -> str:
    """Generate SHA-256 hash of password."""
    return hashlib.sha256(password.encode()).hexdigest()


def _check_password_simple() -> bool:
    """Simple password authentication.
    
    Uses st.secrets or environment variable for password.
    Returns True if authenticated.
    """
    # Get password from secrets or env
    correct_password = None

    # Try Streamlit secrets first
    try:
        if hasattr(st, 'secrets') and "APP_PASSWORD" in st.secrets:
            correct_password = st.secrets["APP_PASSWORD"]
    except Exception:
        pass

    # Fallback to environment variable
    if not correct_password:
        correct_password = os.getenv("APP_PASSWORD")
    
    # If no password is set, skip authentication (development mode)
    if not correct_password:
        return True

    # Initialize session state
    if "password" not in st.session_state:
        st.session_state["password"] = ""
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = None

    def password_entered():
        """Callback when password is entered."""
        entered_password = st.session_state.get("password", "")
        if entered_password and hmac.compare_digest(
            entered_password,
            correct_password
        ):
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]  # Don't store password
        else:
            st.session_state["password_correct"] = False
    
    # First run or password not yet verified
    if st.session_state["password_correct"] is None:
        st.markdown("""
        <style>
            .auth-container {
                max-width: 400px;
                margin: 100px auto;
                padding: 40px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
            .auth-title {
                font-size: 24px;
                font-weight: 600;
                color: #1a1a1a;
                margin-bottom: 8px;
                text-align: center;
            }
            .auth-subtitle {
                font-size: 14px;
                color: #666;
                margin-bottom: 24px;
                text-align: center;
            }
        </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="auth-title">🔐 JTVO Dashboard</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-subtitle">アクセスするにはパスワードを入力してください</div>', unsafe_allow_html=True)
            
            st.text_input(
                "パスワード",
                type="password",
                on_change=password_entered,
                key="password",
                placeholder="パスワードを入力"
            )
            st.button("ログイン", on_click=password_entered, type="primary", use_container_width=True)
        return False
    
    # Password was entered but incorrect
    elif not st.session_state["password_correct"]:
        st.markdown("""
        <style>
            .auth-container {
                max-width: 400px;
                margin: 100px auto;
                padding: 40px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.1);
            }
        </style>
        """, unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown('<div class="auth-title">🔐 JTVO Dashboard</div>', unsafe_allow_html=True)
            st.markdown('<div class="auth-subtitle">アクセスするにはパスワードを入力してください</div>', unsafe_allow_html=True)
            
            st.text_input(
                "パスワード",
                type="password",
                on_change=password_entered,
                key="password",
                placeholder="パスワードを入力"
            )
            st.error("❌ パスワードが正しくありません")
            st.button("ログイン", on_click=password_entered, type="primary", use_container_width=True)
        return False
    
    # Password correct
    return True


def _check_user_credentials() -> bool:
    """Username + Password authentication with multiple users.
    
    Uses st.secrets for user credentials:
    [users]
    admin = "hashed_password"
    user1 = "hashed_password"
    """
    # Get users from secrets
    try:
        users = dict(st.secrets.get("users", {}))
    except Exception:
        users = {}
    
    # If no users defined, skip authentication
    if not users:
        return True
    
    def credentials_entered():
        """Callback when credentials are entered."""
        username = st.session_state.get("username", "")
        password = st.session_state.get("password", "")
        password_hash = _get_password_hash(password)
        
        if username in users and hmac.compare_digest(users[username], password_hash):
            st.session_state["authenticated"] = True
            st.session_state["current_user"] = username
            del st.session_state["password"]
        else:
            st.session_state["authenticated"] = False
    
    # Check if already authenticated
    if st.session_state.get("authenticated", None) is None:
        _show_login_form(credentials_entered)
        return False
    elif not st.session_state["authenticated"]:
        _show_login_form(credentials_entered, show_error=True)
        return False
    
    return True


def _show_login_form(callback, show_error: bool = False):
    """Display the login form."""
    st.markdown("""
    <style>
        .login-container {
            max-width: 400px;
            margin: 80px auto;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
    </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("### 🔐 JTVO Dashboard")
        st.markdown("アクセスするにはログインしてください")
        
        st.text_input("ユーザー名", key="username", placeholder="ユーザー名")
        st.text_input("パスワード", type="password", key="password", placeholder="パスワード")
        
        if show_error:
            st.error("❌ ユーザー名またはパスワードが正しくありません")
        
        st.button("ログイン", on_click=callback, type="primary", use_container_width=True)


def check_authentication(method: str = "password") -> bool:
    """Main authentication function.
    
    Args:
        method: Authentication method - "password", "users", or "none"
    
    Returns:
        True if authenticated, False otherwise
    """
    if method == "none":
        return True
    elif method == "users":
        return _check_user_credentials()
    else:  # default: password
        return _check_password_simple()


def logout():
    """Clear authentication state."""
    for key in ["password_correct", "authenticated", "current_user"]:
        if key in st.session_state:
            del st.session_state[key]


def get_current_user() -> Optional[str]:
    """Get the current authenticated user."""
    return st.session_state.get("current_user")


def require_auth(func):
    """Decorator to require authentication."""
    def wrapper(*args, **kwargs):
        if not check_authentication():
            st.stop()
        return func(*args, **kwargs)
    return wrapper
