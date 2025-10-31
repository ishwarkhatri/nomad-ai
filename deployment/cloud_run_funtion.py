import os
import json
import base64
import psycopg2
import functions_framework
from vertexai import init
from vertexai import agent_engines
from datetime import datetime
import requests
import resend

PROJECT_ID = "the-ragtag-crew-hackathon"
LOCATION = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
AGENT_NAME = "Nomad-AI-ADK-In-trip"

DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_HOST = os.getenv("DB_HOST")

# ✅ Email Configuration
# Supports: Resend, Gmail SMTP, or SendGrid
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "resend")  # Options: resend, gmail, sendgrid
RESEND_API_KEY = 're_ZMNDuYLi_DDzso6R3MFL6igsVAt1U4wPj'
FROM_EMAIL = os.getenv("FROM_EMAIL", "onboarding@resend.dev")  # Default Resend test email
TO_EMAIL = "aakash.khurana1998@gmail.com"

# ✅ Init Vertex AI
init(project=PROJECT_ID, location=LOCATION)

def get_agent():
    apps = agent_engines.list(filter=f'display_name="{AGENT_NAME}"')
    try:
        return next(apps)
    except StopIteration:
        raise RuntimeError(f"❌ ADK agent '{AGENT_NAME}' not found")

REMOTE_AGENT = get_agent()

import json

def create_email_template(agent_response, itinerary_data):
    """Create a beautiful HTML email template with agent's response."""
    
    # Parse itinerary for details
    try:
        itinerary = json.loads(itinerary_data) if isinstance(itinerary_data, str) else itinerary_data
        trip_name = itinerary.get("trip_name", "Your Trip")
        destination = itinerary.get("destination", "Unknown")
        start_date = itinerary.get("start_date", "")
        end_date = itinerary.get("end_date", "")
    except:
        trip_name = "Your Trip"
        destination = "Unknown"
        start_date = ""
        end_date = ""
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 600px;
                margin: 0 auto;
                padding: 0;
                background-color: #f4f4f4;
            }}
            .container {{
                background-color: #ffffff;
                margin: 20px;
                border-radius: 10px;
                overflow: hidden;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header {{
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 30px;
                text-align: center;
            }}
            .header h1 {{
                margin: 0;
                font-size: 28px;
                font-weight: 600;
            }}
            .header p {{
                margin: 10px 0 0 0;
                font-size: 14px;
                opacity: 0.9;
            }}
            .content {{
                padding: 30px;
            }}
            .trip-info {{
                background-color: #f8f9fa;
                border-left: 4px solid #667eea;
                padding: 15px;
                margin: 20px 0;
                border-radius: 4px;
            }}
            .trip-info h3 {{
                margin: 0 0 10px 0;
                color: #667eea;
                font-size: 18px;
            }}
            .trip-info p {{
                margin: 5px 0;
                font-size: 14px;
            }}
            .alert-section {{
                background-color: #fff3cd;
                border: 1px solid #ffc107;
                border-radius: 6px;
                padding: 20px;
                margin: 20px 0;
            }}
            .alert-section h2 {{
                color: #856404;
                margin: 0 0 15px 0;
                font-size: 20px;
            }}
            .alert-content {{
                color: #333;
                white-space: pre-wrap;
                line-height: 1.8;
            }}
            .footer {{
                background-color: #f8f9fa;
                padding: 20px;
                text-align: center;
                font-size: 12px;
                color: #666;
                border-top: 1px solid #e9ecef;
            }}
            .badge {{
                display: inline-block;
                padding: 4px 12px;
                background-color: #667eea;
                color: white;
                border-radius: 12px;
                font-size: 12px;
                font-weight: 600;
                margin-right: 10px;
            }}
            .icon {{
                font-size: 20px;
                margin-right: 8px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🌍 Nomad AI Travel Alert</h1>
                <p>Real-time Itinerary Monitoring</p>
            </div>
            
            <div class="content">
                <div class="trip-info">
                    <h3>📅 {trip_name}</h3>
                    <p><strong>Destination:</strong> {destination}</p>
                    <p><strong>Travel Dates:</strong> {start_date} to {end_date}</p>
                    <p><strong>Status Check:</strong> {datetime.now().strftime("%B %d, %Y at %I:%M %p")}</p>
                </div>
                
                <div class="alert-section">
                    <h2>⚠️ Status Update</h2>
                    <div class="alert-content">{agent_response}</div>
                </div>
                
                <p style="margin-top: 30px; color: #666; font-size: 14px;">
                    This is an automated notification from your Nomad AI travel assistant. 
                    We continuously monitor your itinerary for any changes, delays, or important updates.
                </p>
            </div>
            
            <div class="footer">
                <p>Powered by <strong>Nomad AI</strong> | Intelligent Travel Monitoring</p>
                <p style="margin-top: 10px; font-size: 11px; color: #999;">
                    This email was sent to {TO_EMAIL}
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

def send_email_via_resend(subject, html_content):
    """Send email using Resend API (easiest option)."""
    try:
        if not RESEND_API_KEY:
            print("⚠️ RESEND_API_KEY not configured")
            return False
        
        # Set Resend API key
        resend.api_key = RESEND_API_KEY
        
        # Send email using Resend SDK
        response = resend.Emails.send({
            "from": FROM_EMAIL,
            "to": TO_EMAIL,
            "subject": subject,
            "html": html_content
        })
        
        print(f"✅ Email sent via Resend! ID: {response.get('id')}")
        return True
            
    except Exception as e:
        print(f"❌ Failed to send email via Resend: {e}")
        return False

def send_email_via_gmail(subject, html_content):
    """Send email using Gmail SMTP."""
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        if not GMAIL_USER or not GMAIL_APP_PASSWORD:
            print("⚠️ Gmail credentials not configured")
            return False
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = GMAIL_USER
        msg['To'] = TO_EMAIL
        
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.send_message(msg)
        
        print(f"✅ Email sent via Gmail!")
        return True
        
    except Exception as e:
        print(f"❌ Failed to send email via Gmail: {e}")
        return False

def send_email(subject, html_content):
    """Send email using configured provider."""
    print(f"📧 Attempting to send email via {EMAIL_PROVIDER}...")
    
    if EMAIL_PROVIDER == "resend":
        return send_email_via_resend(subject, html_content)
    elif EMAIL_PROVIDER == "gmail":
        return send_email_via_gmail(subject, html_content)
    else:
        print(f"⚠️ Unknown email provider: {EMAIL_PROVIDER}")
        # Try Resend as fallback
        return send_email_via_resend(subject, html_content)

def notify_agent(itinerary):
    try:
        print("inside notify")

        # itinerary = (<json dict>,)  → we want index 0
        itinerary_json = itinerary[0]

        # ✅ If PostgreSQL returns dict, stringify it
        itinerary_json_string = json.dumps(itinerary_json, default=str)

        print("Serialized itinerary JSON:")
        print(itinerary_json_string)

        # ✅ Replace with correct user id — you *must* pass a user_id to agent
        # If user_id NOT in this query, you must pass separately
        user_id = "test_123123"  # OR get from function argument

        msg = f"Here is the itinerary data: {itinerary_json_string}"

        session = REMOTE_AGENT.create_session(user_id=user_id)
        session_id = session["id"]
        print(f"✅ New session: {session_id}")
        print("akash")
        print(msg)

        events = REMOTE_AGENT.stream_query(
            user_id=user_id,
            session_id=session_id,
            message=msg
        )

        responses = []
        for event in events:
            parts = event.get("content", {}).get("parts", [])
            for part in parts:
                if "text" in part and part["text"].strip():
                    responses.append(part["text"].strip())

        if responses:
            agent_response = responses[-1]
            print("🤖 Agent Response:", agent_response)
            
            # ✅ Send email notification with agent's response
            subject = f"🚨 Travel Alert: {itinerary_json.get('trip_name', 'Your Trip')}"
            html_email = create_email_template(agent_response, itinerary_json)
            send_email(subject, html_email)
        else:
            print("⚠️ No text response from agent")

        print("done ✅")
        return responses[-1] if responses else None

    except Exception as e:
        print(f"❌ Error in notify_agent: {e}")
        return None



@functions_framework.http
def hello_http(request):
    print("✨ Scheduler or Pub/Sub trigger")

    # ✅ Parse Pub/Sub safely
    try:
        envelope = request.get_json(silent=True)
        pubsub_message = base64.b64decode(
            envelope["message"]["data"]
        ).decode("utf-8") if envelope and "message" in envelope else ""

        print(f"📩 Trigger message: {pubsub_message}")

    except Exception as e:
        print(f"⚠️ Could not parse Pub/Sub message: {e}")

    # ✅ Validate DB env
    if not all([DB_USER, DB_PASS, DB_NAME, DB_HOST]):
        msg = "❌ Database env vars missing"
        print(msg)
        return msg, 500

    try:
        conn = psycopg2.connect(
            user=DB_USER,
            password=DB_PASS,
            dbname=DB_NAME,
            host=DB_HOST
        )
        cursor = conn.cursor()

        cursor.execute("SELECT itinerary_data FROM itineraries WHERE start_date = CURRENT_DATE;")
        rows = cursor.fetchall()

        print(f"✅ Found {len(rows)} itineraries starting today")

        for row in rows:
            print("Notify going")
            notify_agent(row)

        cursor.close()
        conn.close()

        return f"✅ Processed {len(rows)} itineraries", 200

    except psycopg2.Error as db_error:
        print(f"🔥 Database error: {db_error}")
        return "DB Failure", 500

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return "Internal Error", 500
