"""Email service for sending HTML briefs over SMTP."""
from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import markdown

from config import Config

logger = logging.getLogger(__name__)


class EmailService:
    """Service to handle markdown rendering and SMTP email dispatch."""

    @classmethod
    def send_brief(cls, recipient_email: str, brief_content: str, full_name: str | None = None) -> bool:
        """Render a markdown brief to HTML and email it to the user.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not Config.SMTP_USER or not Config.SMTP_PASSWORD:
            logger.warning("SMTP credentials not configured. Skipping email dispatch.")
            return False

        name = full_name or recipient_email.split("@")[0]
        subject = f"Your Daily Intelligence Brief - {name}"

        # 1. Convert Markdown to HTML
        try:
            # Render markdown with common extensions (tables, fenced code blocks)
            html_body = markdown.markdown(
                brief_content,
                extensions=["fenced_code", "tables", "nl2br"]
            )
        except Exception as exc:
            logger.error("Failed to parse markdown for email: %s", exc)
            # Simple fallback replacement in case markdown parsing fails
            html_body = brief_content.replace("\n", "<br>")

        # 2. Build the HTML template wrapper
        html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{subject}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            line-height: 1.6;
            color: #1e293b;
            background-color: #f8fafc;
            margin: 0;
            padding: 0;
            -webkit-font-smoothing: antialiased;
        }}
        .wrapper {{
            max-width: 680px;
            margin: 0 auto;
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 8px;
            overflow: hidden;
            margin-top: 20px;
            margin-bottom: 20px;
        }}
        .header {{
            background-color: #0f172a;
            color: #ffffff;
            padding: 24px 32px;
            text-align: left;
        }}
        .header h1 {{
            margin: 0;
            font-size: 22px;
            font-weight: 600;
            letter-spacing: -0.025em;
        }}
        .header p {{
            margin: 4px 0 0 0;
            font-size: 14px;
            color: #94a3b8;
        }}
        .content {{
            padding: 32px;
            font-size: 16px;
        }}
        .content h2 {{
            font-size: 18px;
            font-weight: 600;
            color: #0f172a;
            margin-top: 28px;
            margin-bottom: 12px;
            border-bottom: 1px solid #f1f5f9;
            padding-bottom: 6px;
        }}
        .content p {{
            margin-top: 0;
            margin-bottom: 16px;
        }}
        .content a {{
            color: #2563eb;
            text-decoration: none;
        }}
        .content a:hover {{
            text-decoration: underline;
        }}
        .content blockquote {{
            margin: 16px 0;
            padding-left: 16px;
            border-left: 4px solid #cbd5e1;
            color: #475569;
            font-style: italic;
        }}
        .footer {{
            background-color: #f1f5f9;
            padding: 16px 32px;
            text-align: center;
            font-size: 12px;
            color: #64748b;
            border-top: 1px solid #e2e8f0;
        }}
    </style>
</head>
<body>
    <div class="wrapper">
        <div class="header">
            <h1>markly radar</h1>
            <p>Your Daily Intelligence Briefing</p>
        </div>
        <div class="content">
            {html_body}
        </div>
        <div class="footer">
            Sent by Markly RSS Radar. To manage your sources, open the Markly app.
        </div>
    </div>
</body>
</html>
"""

        # 3. Create the email message container
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = Config.SMTP_FROM
        msg["To"] = recipient_email

        # Fallback plain-text version
        text_content = brief_content
        
        part1 = MIMEText(text_content, "plain", "utf-8")
        part2 = MIMEText(html_content, "html", "utf-8")
        
        msg.attach(part1)
        msg.attach(part2)

        # 4. Connect and send
        try:
            logger.info("Connecting to SMTP server %s:%s", Config.SMTP_HOST, Config.SMTP_PORT)
            if Config.SMTP_PORT == 465:
                server = smtplib.SMTP_SSL(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
            else:
                server = smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=15)
                # Secure the connection using TLS
                server.ehlo()
                server.starttls()
                server.ehlo()

            # Authenticate
            server.login(Config.SMTP_USER, Config.SMTP_PASSWORD)
            
            # Send
            server.sendmail(Config.SMTP_FROM, recipient_email, msg.as_string())
            server.quit()
            
            logger.info("Successfully sent brief email to %s", recipient_email)
            return True
            
        except Exception as exc:
            logger.error("Failed to send brief email to %s: %s", recipient_email, exc)
            return False
