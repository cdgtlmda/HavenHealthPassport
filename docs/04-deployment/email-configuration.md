# Email Service Configuration

## Overview

The Haven Health Passport email service supports multiple providers, rate limiting, templates with localization, and comprehensive tracking capabilities.

## Supported Providers

### AWS SES (Default)

To use AWS SES for email sending:

```bash
# Set email provider
EMAIL_PROVIDER=ses

# AWS configuration (if not using IAM roles)
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-1

# Optional: SES Configuration Set for tracking
SES_CONFIGURATION_SET=haven-health-emails

# From email address (must be verified in SES)
FROM_EMAIL=noreply@havenhealthpassport.org
FROM_NAME="Haven Health Passport"
```

### SendGrid

To use SendGrid for email sending:

```bash
# Set email provider
EMAIL_PROVIDER=sendgrid

# SendGrid API key
SENDGRID_API_KEY=your_sendgrid_api_key

# Optional: Webhook verification key
SENDGRID_WEBHOOK_KEY=your_webhook_key

# From email address
FROM_EMAIL=noreply@havenhealthpassport.org
FROM_NAME="Haven Health Passport"
```

## Rate Limiting

Configure email rate limits to prevent abuse:

```bash
# Rate limiting settings
EMAIL_RATE_PER_MINUTE=10
EMAIL_RATE_PER_HOUR=100
EMAIL_RATE_PER_DAY=1000
EMAIL_RATE_PER_RECIPIENT_HOUR=3
EMAIL_BURST_SIZE=20
```

## Email Templates

### Template Structure

Templates are organized by language:
```
src/services/email/templates/
├── templates.json          # Template metadata
├── en/                     # English templates
│   ├── verify_email.html
│   ├── verify_email.txt
│   ├── password_reset.html
│   └── ...
├── es/                     # Spanish templates
├── fr/                     # French templates
├── ar/                     # Arabic templates
└── zh/                     # Chinese templates
```

### Available Templates

1. **verify_email** - Email verification
2. **password_reset** - Password reset request
3. **report_ready** - Report generation complete
4. **appointment_reminder** - Upcoming appointment
5. **medication_reminder** - Medication schedule
6. **health_alert** - Important health notifications
7. **welcome** - Welcome after verification
8. **data_export_ready** - Data export complete
9. **security_alert** - Security notifications
10. **record_shared** - Health record sharing

### Creating New Templates

1. Create HTML and text versions in appropriate language folders
2. Update `templates.json` with template metadata
3. Use Jinja2 template syntax for variables

Example template:
```html
<!DOCTYPE html>
<html lang="{{ language }}">
<head>
    <meta charset="UTF-8">
    <title>{{ subject }}</title>
</head>
<body>
    <h1>Hello {{ user_name }}</h1>
    <p>{{ message_content }}</p>
</body>
</html>
```

## Email Tracking

### Bounce Handling

Configure webhook endpoints:

**AWS SES**: Set up SNS topic and subscription
```bash
# In AWS Console:
1. Create SNS topic for bounces/complaints
2. Subscribe your endpoint: https://api.yourdomain.com/webhooks/ses
3. Configure SES to use the SNS topic
```

**SendGrid**: Configure Event Webhook
```bash
# In SendGrid Console:
1. Go to Settings > Mail Settings > Event Webhook
2. Set HTTP POST URL: https://api.yourdomain.com/webhooks/sendgrid
3. Select events: Bounce, Spam Report, etc.
```

### Email Analytics

Track email metrics:
- Sent count
- Delivery rate
- Open rate (with tracking pixel)
- Click rate (with link tracking)
- Bounce rate
- Complaint rate

## API Usage

### Basic Email

```python
from src.services.email import get_email_service

email_service = get_email_service()

# Send simple email
result = await email_service.send_email(
    to="user@example.com",
    subject="Test Email",
    html_body="<p>Hello World</p>",
    text_body="Hello World"
)
```

### Template Email

```python
# Send with template
result = await email_service.send_email(
    to="user@example.com",
    subject="Verify Your Email",
    template_id="verify_email",
    template_params={
        "user_name": "John Doe",
        "verification_url": "https://example.com/verify?token=123"
    },
    language="es"  # Spanish version
)
```

### Bulk Email

```python
# Send multiple emails
messages = [
    {
        "to": "user1@example.com",
        "subject": "Newsletter",
        "template_id": "newsletter",
        "template_params": {"name": "User 1"}
    },
    {
        "to": "user2@example.com",
        "subject": "Newsletter",
        "template_id": "newsletter",
        "template_params": {"name": "User 2"}
    }
]

results = await email_service.send_bulk_emails(messages)
```

## Legacy Support

The original `EmailService` class is maintained for backward compatibility but now uses the enhanced service internally. All new code should use `get_email_service()`.

## Security Considerations

1. **Email Verification**: Always verify sender email addresses with your provider
2. **Rate Limiting**: Prevents abuse and protects sender reputation
3. **Unsubscribe Handling**: Automatic tracking and compliance
4. **PHI Protection**: Never include PHI in email subjects
5. **Encryption**: Use TLS for all email transmission
6. **Authentication**: Implement SPF, DKIM, and DMARC records

## Monitoring

Monitor email service health:

```python
# Check provider connection
connected = await email_service.test_connection()

# Get rate limit status
usage = email_service.rate_limiter.get_current_usage()

# Get email statistics
stats = await email_service.get_email_stats(
    start_date=datetime(2024, 1, 1),
    template_id="verify_email"
)
```

## Troubleshooting

### Common Issues

1. **Rate Limit Exceeded**
   - Check current usage with `get_current_usage()`
   - Adjust rate limits if needed
   - Implement retry logic

2. **Template Not Found**
   - Verify template exists in correct language folder
   - Check template name in templates.json
   - Ensure template syntax is valid

3. **Delivery Issues**
   - Verify sender email is authenticated
   - Check bounce/complaint rates
   - Review provider logs

4. **Webhook Failures**
   - Verify webhook URL is accessible
   - Check webhook signature validation
   - Review webhook logs

## Development Mode

For local development without sending real emails:

```bash
# Use localhost SMTP (emails will be logged only)
SMTP_HOST=localhost
EMAIL_PROVIDER=ses  # Still use provider for template features
```