import os
import logging
import urllib.parse
import urllib.request
import json

logger = logging.getLogger(__name__)

def send_sms_otp(phone_number: str, otp_code: str) -> dict:
    """
    Sends a real SMS OTP to the customer's mobile number.
    Supports:
    1. Fast2SMS (Indian numbers - easiest setup with quick free trial credits)
    2. Twilio (International/Indian)
    3. Console / Dev mode fallback (when no SMS API key is configured)
    """
    # Clean phone number to 10 digits for Indian providers
    digits_only = ''.join(c for c in phone_number if c.isdigit())
    ten_digit_phone = digits_only[-10:] if len(digits_only) >= 10 else digits_only

    # Check for Fast2SMS API Key
    fast2sms_key = os.getenv('FAST2SMS_API_KEY', '').strip()
    if fast2sms_key:
        try:
            url = f"https://www.fast2sms.com/dev/bulkV2"
            data = urllib.parse.urlencode({
                'authorization': fast2sms_key,
                'variables_values': otp_code,
                'route': 'otp',
                'numbers': ten_digit_phone
            }).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=8) as response:
                resp_data = json.loads(response.read().decode('utf-8'))
                if resp_data.get('return'):
                    logger.info(f"[SMS SUCCESS] Fast2SMS sent OTP to {phone_number}")
                    return {'success': True, 'provider': 'fast2sms'}
                else:
                    logger.error(f"[SMS ERROR] Fast2SMS error: {resp_data}")
        except Exception as e:
            logger.error(f"[SMS EXCEPTION] Fast2SMS failed: {e}")

    # Check for Twilio API Credentials
    twilio_sid = os.getenv('TWILIO_ACCOUNT_SID', '').strip()
    twilio_token = os.getenv('TWILIO_AUTH_TOKEN', '').strip()
    twilio_from = os.getenv('TWILIO_PHONE_NUMBER', '').strip()
    if twilio_sid and twilio_token and twilio_from:
        try:
            import base64
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_sid}/Messages.json"
            formatted_phone = phone_number if phone_number.startswith('+') else f'+91{ten_digit_phone}'
            data = urllib.parse.urlencode({
                'To': formatted_phone,
                'From': twilio_from,
                'Body': f"Your Rayara Café verification code is: {otp_code}. Valid for 10 minutes."
            }).encode('utf-8')
            auth_str = f"{twilio_sid}:{twilio_token}"
            auth_header = 'Basic ' + base64.b64encode(auth_str.encode('ascii')).decode('ascii')
            req = urllib.request.Request(url, data=data, headers={'Authorization': auth_header})
            with urllib.request.urlopen(req, timeout=8) as response:
                logger.info(f"[SMS SUCCESS] Twilio sent OTP to {formatted_phone}")
                return {'success': True, 'provider': 'twilio'}
        except Exception as e:
            logger.error(f"[SMS EXCEPTION] Twilio failed: {e}")

    # Development fallback: log to console
    print(f"\n========================================")
    print(f"[RAYARA SMS OTP] Mobile: {phone_number} | OTP: {otp_code}")
    print(f"(To send real SMS to mobile, set FAST2SMS_API_KEY in .env)")
    print(f"========================================\n")
    return {'success': True, 'provider': 'console_dev'}

