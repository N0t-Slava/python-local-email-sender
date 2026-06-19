# Amazon SES Configuration Guide

Use this guide when the app must send real email through Amazon SES instead of
local MailHog.

## 0. Choose One Region

Use one SES region everywhere. Example:

```text
eu-central-1
```

The same region must be used for:

- SES identities
- SES SMTP endpoint
- AWS Secrets Manager secret
- `AWS_REGION` in the app environment

For `eu-central-1`, the SES SMTP endpoint is:

```text
email-smtp.eu-central-1.amazonaws.com
```

## 1. Move SES Out Of Sandbox

In a new AWS account, SES starts in sandbox mode. Sandbox mode can only send to
verified recipients.

In AWS Console:

```text
Amazon SES -> Account dashboard -> Request production access
```

Use:

```text
Mail type: Transactional or Marketing
Website URL: your real site
Use case: explain your opt-in process and bounce/complaint handling
```

You can configure DNS before production access is approved, but real sends are
limited until approval.

## 2. Verify The Sending Domain

In AWS Console:

```text
Amazon SES -> Verified identities -> Create identity
```

Use:

```text
Identity type: Domain
Domain: example.com
DKIM: Easy DKIM
DKIM key length: RSA_2048_BIT
```

Do not use BYODKIM unless you specifically need to manage DKIM keys yourself.

## 3. Add DKIM DNS Records

SES shows three DKIM CNAME records.

If SES shows:

```text
Name:  abc123._domainkey.example.com
Value: abc123.dkim.amazonses.com
```

Add this DNS record:

```text
Type:  CNAME
Name:  abc123._domainkey
Value: abc123.dkim.amazonses.com
TTL:   Auto / default
```

Repeat for all three DKIM records.

Wait until SES shows DKIM status as successful.

## 4. Add SPF For The Sending Domain

Add one SPF TXT record for the root sending domain:

```text
Type:  TXT
Name:  @
Value: v=spf1 include:amazonses.com -all
TTL:   Auto / default
```

Important: a DNS name must not have two separate `v=spf1` records. If the domain
already has SPF, merge SES into the existing record.

Example merged SPF:

```text
v=spf1 include:_spf.google.com include:amazonses.com -all
```

## 5. Add DMARC

Start with monitoring mode:

```text
Type:  TXT
Name:  _dmarc
Value: v=DMARC1; p=none; rua=mailto:dmarc@example.com
TTL:   Auto / default
```

After real traffic is stable, move gradually:

```text
p=none -> p=quarantine -> p=reject
```

Use a real mailbox or DMARC report service for `rua`.

## 6. Configure Custom MAIL FROM

In SES, open the domain identity and configure custom MAIL FROM:

```text
MAIL FROM domain: mail.example.com
Behavior on MX failure: Use default MAIL FROM domain
```

For `eu-central-1`, SES asks for this MX target:

```text
feedback-smtp.eu-central-1.amazonses.com
```

Add DNS:

```text
Type:     MX
Name:     mail
Value:    feedback-smtp.eu-central-1.amazonses.com
Priority: 10
TTL:      Auto / default
```

Also add SPF for the MAIL FROM subdomain:

```text
Type:  TXT
Name:  mail
Value: v=spf1 include:amazonses.com -all
TTL:   Auto / default
```

Expected records:

```text
mail.example.com MX  10 feedback-smtp.eu-central-1.amazonses.com
mail.example.com TXT "v=spf1 include:amazonses.com -all"
```

Wait until SES shows custom MAIL FROM status as successful.

## 7. Create SES SMTP Credentials

In AWS Console:

```text
Amazon SES -> SMTP settings -> Create SMTP credentials
```

Save:

```text
SMTP username
SMTP password
```

These are not the same as normal AWS access keys.

## 8. Store SMTP Credentials In Secrets Manager

Create a secret in the same AWS region.

Recommended secret name:

```text
email-service/production/smtp
```

Secret value:

```json
{
  "host": "email-smtp.eu-central-1.amazonaws.com",
  "port": 587,
  "username": "SES_SMTP_USERNAME",
  "password": "SES_SMTP_PASSWORD",
  "from_email": "hello@example.com"
}
```

The app also accepts env-style keys:

```json
{
  "SMTP_HOST": "email-smtp.eu-central-1.amazonaws.com",
  "SMTP_PORT": "587",
  "SMTP_USER": "SES_SMTP_USERNAME",
  "SMTP_PASS": "SES_SMTP_PASSWORD",
  "FROM_EMAIL": "hello@example.com"
}
```

`from_email` / `FROM_EMAIL` must use the verified sending domain.

## 9. Give The App Read Access To The Secret

The app runtime role only needs read access to this exact secret.

Replace `ACCOUNT_ID`, region, and secret name:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadSmtpSecret",
      "Effect": "Allow",
      "Action": [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret"
      ],
      "Resource": "arn:aws:secretsmanager:eu-central-1:ACCOUNT_ID:secret:email-service/production/smtp-*"
    }
  ]
}
```

Do not give the application delete/write secret permissions.

## 10. Configure App Environment

Production/staging:

```env
APP_ENV=production
AWS_REGION=eu-central-1
SECRETS_BACKEND=aws
SMTP_SECRET_ID=email-service/production/smtp
SMTP_SECRET_CACHE_SECONDS=300
SES_PREFLIGHT_ENABLED=true
PUBLIC_API_BASE_URL=https://api.example.com
UNSUBSCRIBE_SECRET=replace-with-long-random-secret
```

Local Docker test mode must keep SES preflight disabled:

```env
APP_ENV=development
SECRETS_BACKEND=env
SES_PREFLIGHT_ENABLED=false
SMTP_HOST=mailhog
SMTP_PORT=1025
FROM_EMAIL=test@example.com
```

## 11. Add The Domain In The App

Open the app Settings page:

```text
Settings -> Sending Domains
```

Add:

```text
Domain: example.com
MAIL FROM domain: mail.example.com
```

Click refresh.

Expected statuses:

```text
SES verification: Valid
DKIM: Valid
SPF: Valid
DMARC: Valid
MAIL FROM: Valid
```

## 12. Check A Sender Before Sending

Use Settings pre-send checker or call the API:

```bash
curl -X POST http://localhost:8000/domains/check-sending \
  -H "Content-Type: application/json" \
  -d '{"from_email":"hello@example.com"}'
```

Expected successful response:

```json
{
  "can_send": true,
  "from_email": "hello@example.com",
  "domain": "example.com",
  "blockers": [],
  "warnings": []
}
```

Campaign sending is blocked when `SES_PREFLIGHT_ENABLED=true` and the sending
domain is not ready.

## 13. Send A Real Test Email

After all statuses are valid:

```bash
curl -X POST http://localhost:8000/send_email \
  -H "Content-Type: application/json" \
  -d '{"email":"recipient@example.net","from_email":"hello@example.com","subject":"SES smoke test","body":"Hello from SES"}'
```

Check:

- API logs
- SES sending metrics
- recipient inbox
- spam folder

## 14. Optional Bounce And Complaint Webhooks

For production, configure SES event publishing through SNS.

Recommended environment:

```env
SES_CONFIGURATION_SET=email-service-production
SNS_SES_TOPIC_ARN=arn:aws:sns:eu-central-1:ACCOUNT_ID:ses-events
```

Point SNS notifications to:

```text
POST https://api.example.com/webhooks/aws/sns/ses
```

Track at least:

- Bounce
- Complaint
- Delivery

## 15. Rotate SMTP Credentials

1. Create new SES SMTP credentials.
2. Update the Secrets Manager secret.
3. Wait `SMTP_SECRET_CACHE_SECONDS` or restart `web` and `worker`.
4. Send a test email.
5. Delete the old SES SMTP credentials.
6. Watch logs for SMTP authentication errors.

The app clears the cached SMTP secret and retries once if SMTP authentication
fails.

## Troubleshooting

`SMTP authentication failed`

- Secret has the wrong SES SMTP username/password.
- Secret is in the wrong AWS region.
- App role cannot read `SMTP_SECRET_ID`.

`Sender not verified`

- `from_email` does not use a verified SES identity.
- SES identity is verified in another region.

`MAIL FROM failed`

- MX record for `mail.example.com` is missing or wrong.
- MAIL FROM SPF TXT record is missing.

`SPF failed`

- There are two separate SPF TXT records for the same DNS name.
- Existing SPF was not merged with `include:amazonses.com`.

`Campaign saved but does not send`

- Worker is not running.
- RabbitMQ/Redis is not reachable.
- `SES_PREFLIGHT_ENABLED=true` and domain status is not valid.
- SES account is still in sandbox.
