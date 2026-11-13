import logging
import json
import urllib.request
import urllib.error
from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

def send_resend_email(to_email: str, subject: str, html_content: str, text_content: str) -> dict:
    """
    Directly sends transactional email using Resend API.
    Uses User-Agent: resend-python/2.6.0 to pass Cloudflare filters.
    """
    api_key = getattr(settings, 'RESEND_API_KEY', '').strip()
    from_email = getattr(settings, 'RESEND_FROM_EMAIL', 'Rayara Café <onboarding@resend.dev>').strip()

    if not api_key:
        return {'success': False, 'error': 'No Resend API key configured'}

    url = 'https://api.resend.com/emails'
    payload = {
        'from': from_email,
        'to': [to_email],
        'subject': subject,
        'html': html_content,
        'text': text_content,
    }
    data = json.dumps(payload).encode('utf-8')
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
        'User-Agent': 'resend-python/2.6.0',
    }

    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp_body = response.read().decode('utf-8')
            res_json = json.loads(resp_body)
            email_id = res_json.get('id')
            logger.info(f"[RESEND SUCCESS] Sent email to {to_email}, id: {email_id}")
            return {'success': True, 'mode': 'resend', 'id': email_id}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode('utf-8')
        logger.error(f"[RESEND HTTP ERROR {e.code}] {err_msg}")
        try:
            parsed = json.loads(err_msg)
            message = parsed.get('message', err_msg)
        except Exception:
            message = err_msg
        return {'success': False, 'error': message, 'code': e.code}
    except Exception as e:
        logger.error(f"[RESEND ERROR] {e}")
        return {'success': False, 'error': str(e)}

def send_email_otp(recipient_email: str, otp_code: str) -> dict:
    """
    Sends a 6-digit verification code to the customer's email.
    Priority:
    1. Resend API (Fast, high deliverability, 3000 free emails/month)
    2. Django SMTP (if configured)
    3. Console / Dev Mode (fallback)
    """
    subject = f"Your Rayara Café Login Code: {otp_code}"

    # Plain text version for email clients that do not render HTML
    text_message = (
        f"RAYARA CAFÉ - PLAY & DINE\n\n"
        f"Your verification code is: {otp_code}\n\n"
        f"This code is valid for 10 minutes.\n"
        f"Enter this code on the Rayara app to play and claim your daily dining reward!\n\n"
        f"If you did not request this code, you can safely ignore this email.\n"
    )

    # Branded luxury HTML email version matching the illuminated Rayara signage
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <title>Rayara Verification Code</title>
    </head>
    <body style="margin: 0; padding: 0; background-color: #f5efe6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #22140c;">
      <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5efe6; padding: 30px 15px;">
        <tr>
          <td align="center">
            <table width="100%" max-width="500" cellpadding="0" cellspacing="0" style="max-width: 500px; background-color: #ffffff; border-radius: 24px; overflow: hidden; box-shadow: 0 10px 30px rgba(42, 24, 16, 0.08); border: 1px solid #dfd2c0;">
              <!-- Header with Backlit Rayara Bronze & Amber Glow -->
              <tr>
                <td style="background-color: #2a1810; padding: 35px 25px 30px; text-align: center; border-bottom: 2px solid #e59a38;">
                  <div style="color: #f5a623; font-size: 28px; line-height: 1; text-shadow: 0 0 12px rgba(229, 154, 56, 0.6);">رايارة</div>
                  <div style="color: #ffffff; font-size: 24px; font-weight: bold; letter-spacing: 6px; margin-top: 6px; font-family: Georgia, serif; text-shadow: 0 0 15px rgba(229, 154, 56, 0.4);">RAYARA</div>
                  <div style="color: #e59a38; font-size: 11px; letter-spacing: 6px; margin-top: 6px;">— C A F É —</div>
                </td>
              </tr>
              <!-- Body Content -->
              <tr>
                <td style="padding: 35px 30px; text-align: center;">
                  <h1 style="color: #2a1810; font-size: 22px; font-weight: bold; margin: 0 0 10px; font-family: Georgia, serif;">Your Verification Code</h1>
                  <p style="color: #6d5b50; font-size: 13px; line-height: 1.6; margin: 0 0 25px;">
                    Use this one-time passcode to sign in to <b>Rayara Play &amp; Dine</b> and claim your daily dining reward.
                  </p>

                  <!-- OTP Display Box with Warm Amber Border -->
                  <div style="background-color: #faf6f0; border: 2px dashed #d97d26; border-radius: 16px; padding: 18px 10px; margin: 0 auto 25px; max-width: 320px; box-shadow: 0 0 20px rgba(229, 154, 56, 0.15);">
                    <div style="font-family: 'Courier New', Courier, monospace; font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #2a1810;">
                      {otp_code}
                    </div>
                  </div>

                  <p style="color: #8c786a; font-size: 12px; margin: 0 0 8px;">
                    ⏱️ Code valid for <b>10 minutes</b>.
                  </p>
                  <p style="color: #4e5d42; font-size: 11px; margin: 0; font-weight: 500;">
                    🌿 1 game play eligible every 24 hours per email address.
                  </p>
                </td>
              </tr>
              <!-- Footer -->
              <tr>
                <td style="background-color: #f5efe6; padding: 20px 25px; text-align: center; border-top: 1px solid #dfd2c0;">
                  <p style="color: #8c786a; font-size: 11px; margin: 0; line-height: 1.5;">
                    <b>Rayara Café</b> · Good food. Great moments.<br>
                    Freshly made · Warmly served
                  </p>
                </td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </body>
    </html>
    """

    # 1. Try Resend if configured
    if getattr(settings, 'RESEND_API_KEY', None):
        resend_result = send_resend_email(recipient_email, subject, html_message, text_message)
        if resend_result.get('success'):
            print(f"\n========================================")
            print(f"[RAYARA RESEND] Real email dispatched to: {recipient_email} (ID: {resend_result.get('id')})")
            print(f"========================================\n")
            return resend_result
        else:
            # Resend failed (e.g. unverified domain or test account restriction)
            logger.warning(f"[RESEND FALLBACK] {resend_result.get('error')}")

    # 2. Try Django SMTP if configured
    if getattr(settings, 'EMAIL_HOST_USER', None):
        try:
            send_mail(
                subject=subject,
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient_email],
                html_message=html_message,
                fail_silently=False
            )
            return {'success': True, 'mode': 'smtp'}
        except Exception as e:
            logger.error(f"[SMTP ERROR] {e}")

    # 3. Console fallback for local dev
    print(f"\n========================================")
    print(f"[RAYARA OTP DEV] Email: {recipient_email} | OTP: {otp_code}")
    print(f"========================================\n")
    return {'success': True, 'mode': 'console'}
