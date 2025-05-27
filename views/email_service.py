from flask import current_app, render_template
from flask_mail import Message
from app import mail
from datetime import datetime
import time

def send_verification_email(email, verification_url):
    """Send email verification email with retry logic"""
    msg = Message(
        subject="Verify Your Email Address",
        recipients=[email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    msg.body = f"""
    Please click the following link to verify your email address:
    {verification_url}
    
    This link will expire in 24 hours.
    """
    
    msg.html = render_template(
        'email/verify_email.html',
        verification_url=verification_url,
        year=datetime.now().year
    )
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            mail.send(msg)
            current_app.logger.info(f"Verification email sent to {email}")
            return True
        except Exception as e:
            current_app.logger.error(f"Attempt {attempt + 1} failed to send email to {email}: {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(2)  # wait before retrying
                continue
            current_app.logger.error(f"Failed to send verification email after {max_retries} attempts")
            return False