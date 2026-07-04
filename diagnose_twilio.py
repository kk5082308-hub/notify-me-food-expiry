import os
import sys
from twilio.rest import Client

def main():
    print("====================================================")
    # 1. Inspect Environment Variables
    sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    from_num = os.environ.get('TWILIO_PHONE_NUMBER', '')
    
    print("Checking Environment Variables:")
    print(f"  TWILIO_ACCOUNT_SID: {sid[:6]}... (Length: {len(sid)} characters)" if sid else "  TWILIO_ACCOUNT_SID: NOT SET")
    print(f"  TWILIO_AUTH_TOKEN:  {'*' * 6}... (Length: {len(token)} characters)" if token else "  TWILIO_AUTH_TOKEN:  NOT SET")
    print(f"  TWILIO_PHONE_NUMBER: {from_num}" if from_num else "  TWILIO_PHONE_NUMBER: NOT SET")
    print("----------------------------------------------------")
    
    if not sid or not token or not from_num:
        print("❌ Error: Missing Twilio environment variables.")
        print("Please configure them in this terminal window using:")
        print("  $env:TWILIO_ACCOUNT_SID=\"your_sid\"")
        print("  $env:TWILIO_AUTH_TOKEN=\"your_token\"")
        print("  $env:TWILIO_PHONE_NUMBER=\"your_twilio_number\"")
        return

    # 2. Get target recipient phone number from command line arg or input
    recipient = ""
    if len(sys.argv) > 1:
        recipient = sys.argv[1]
    else:
        recipient = input("Enter verified phone number to send test SMS (e.g. +91767654232x): ").strip()
        
    if not recipient:
        print("❌ Error: No recipient phone number provided.")
        return
        
    print(f"Sending test SMS to: {recipient}...")
    
    try:
        client = Client(sid, token)
        message = client.messages.create(
            body="Notify-Me Trial Verification: Test SMS Sent Successfully!",
            from_=from_num,
            to=recipient
        )
        print("----------------------------------------------------")
        print("✅ Success! Twilio message created successfully.")
        print(f"  Message SID: {message.sid}")
        print(f"  Status:      {message.status}")
    except Exception as e:
        print("----------------------------------------------------")
        print("❌ SMS Send Failed!")
        print(f"  Error message: {e}")
        print("\nCommon Causes & How to Fix:")
        print("1. [HTTP 400] 'The number is not a valid phone number' or similar:")
        print("   - Ensure the country code is correct and the number has the proper digit length.")
        print("2. [HTTP 400] 'The number is unverified':")
        print("   - In Free Trial mode, Twilio only allows sending to numbers added in 'Verified Caller IDs' in your Twilio Console.")
        print("3. [HTTP 400] 'Permission to send an SMS has not been enabled for the region':")
        print("   - Log in to Twilio Console, go to SMS -> Settings -> Geo-Permissions, find your country (e.g., India), check the box to enable it, and save settings.")
    print("====================================================")

if __name__ == '__main__':
    main()
