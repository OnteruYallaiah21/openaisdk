import smtplib
from email.message import EmailMessage
from typing import Optional, List, Dict, Any, Union
import os
import re
import json
import logging
from datetime import datetime
from dotenv import load_dotenv

class EmailSender:
    """Class to send emails with resume attachments"""
    
    def __init__(self, sender_email: str = None, app_password: str = None, resume_file: str = None):
        # Credentials should be provided explicitly (loaded from email.json by the caller)
        # No fallback to environment variables - always use email.json
        self.sender_email = sender_email or ''
        self.app_password = app_password or ''
        self.resume_file = resume_file or ''
    
    def send_email(self, recruiter_email: str, recruiter_name: str, subject: str, body: str, 
                   attach_resume: bool = True, cc: Optional[Union[str, List[str]]] = None, 
                   bcc: Optional[Union[str, List[str]]] = None, body_html: Optional[str] = None) -> bool:
        """
        Send email to recruiter with resume attachment
        
        Args:
            recruiter_email: Email address of the recruiter
            recruiter_name: Name of the recruiter
            subject: Email subject
            body: Email body (plain text)
            attach_resume: Whether to attach resume file
            cc: CC email addresses (string with comma-separated emails or list)
            bcc: BCC email addresses (string with comma-separated emails or list)
            body_html: Optional HTML version of the email body
            
        Returns:
            bool: True if email sent successfully, False otherwise
        """
        try:
            # Compose message
            msg = EmailMessage()
            msg['Subject'] = subject
            msg['From'] = self.sender_email
            msg['To'] = recruiter_email
            
            # Handle CC
            if cc:
                if isinstance(cc, str):
                    # Split comma-separated emails and strip whitespace
                    cc_list = [email.strip() for email in cc.split(',') if email.strip()]
                    if cc_list:
                        msg['Cc'] = ', '.join(cc_list)
                elif isinstance(cc, list):
                    cc_list = [email.strip() for email in cc if email.strip()]
                    if cc_list:
                        msg['Cc'] = ', '.join(cc_list)
            
            # Handle BCC
            if bcc:
                if isinstance(bcc, str):
                    # Split comma-separated emails and strip whitespace
                    bcc_list = [email.strip() for email in bcc.split(',') if email.strip()]
                    if bcc_list:
                        msg['Bcc'] = ', '.join(bcc_list)
                elif isinstance(bcc, list):
                    bcc_list = [email.strip() for email in bcc if email.strip()]
                    if bcc_list:
                        msg['Bcc'] = ', '.join(bcc_list)
            
            # Set both plain text and HTML content if HTML is provided
            if body_html:
                msg.set_content(body)
                msg.add_alternative(body_html, subtype='html')
            else:
                msg.set_content(body)

            # Attach resume if requested and file exists
            if attach_resume and os.path.exists(self.resume_file):
                # Use original filename if set, otherwise use the file path basename
                # This preserves the original filename for ALL users regardless of their system
                attachment_filename = getattr(self, '_original_filename', None) or os.path.basename(self.resume_file)
                print(f"Attaching: {attachment_filename}")
                
                # Detect file type from extension to set correct MIME type
                file_ext = os.path.splitext(attachment_filename.lower())[1]
                if file_ext == '.pdf':
                    maintype, subtype = 'application', 'pdf'
                elif file_ext in ['.doc', '.docx']:
                    maintype, subtype = 'application', 'vnd.openxmlformats-officedocument.wordprocessingml.document' if file_ext == '.docx' else 'msword'
                else:
                    # Default to PDF if unknown
                    maintype, subtype = 'application', 'pdf'
                
                with open(self.resume_file, 'rb') as f:
                    msg.add_attachment(
                        f.read(), 
                        maintype=maintype, 
                        subtype=subtype, 
                        filename=attachment_filename
                    )
            
            # Send email
            with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
                smtp.login(self.sender_email, self.app_password)
                smtp.send_message(msg)
            print(f"✅ Sent to {recruiter_name} at {recruiter_email}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send to {recruiter_email}: {e}")
            return False
    
    def send_bulk_emails(self, recruiter_contacts: dict, subject: str, body: str, 
                         attach_resume: bool = True) -> List[dict]:
        """
        Send emails to multiple recruiters
        
        Args:
            recruiter_contacts: Dictionary with {email: name} pairs
            subject: Email subject
            body: Email body (can use {name} placeholder)
            attach_resume: Whether to attach resume file
            
        Returns:
            List of results for each email sent
        """
        results = []
        for email, name in recruiter_contacts.items():
            # Replace {name} placeholder in body if present
            personalized_body = body.format(name=name) if '{name}' in body else body
            
            success = self.send_email(email, name, subject, personalized_body, attach_resume)
            results.append({
                'email': email,
                'name': name,
                'success': success
            })
        return results
    


# Example usage (for testing)
if __name__ == "__main__":
    sender = EmailSender()
   