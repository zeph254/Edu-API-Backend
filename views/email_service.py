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
# Update emailservice.py with these additions

def send_welcome_email(email, account_type):
    """Send welcome email after profile completion"""
    msg = Message(
        subject=f"Welcome to Our School System ({account_type.capitalize()})",
        recipients=[email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    if account_type == 'teacher':
        msg.body = "Your teacher account has been created and is pending admin approval."
        msg.html = render_template('email/welcome_teacher.html')
    else:
        msg.body = "Your parent account has been created successfully."
        msg.html = render_template('email/welcome_parent.html')
    
    mail.send(msg)

def send_approval_notification(email, approved=True):
    """Send notification when account is approved/rejected"""
    msg = Message(
        subject="Your Account Status Update",
        recipients=[email],
        sender=current_app.config['MAIL_DEFAULT_SENDER']
    )
    
    if approved:
        msg.body = "Your account has been approved by the administrator."
        msg.html = render_template('email/account_approved.html')
    else:
        msg.body = "Your account requires additional information for approval."
        msg.html = render_template('email/account_rejected.html')
    
    mail.send(msg)        