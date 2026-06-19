# Mailflow Local Test Launch

This is the fastest way to run the backend with local Docker services and test
email sending through MailHog. It does not require Amazon SES.

## Requirements

- Docker with Docker Compose
- Port `8000` free for the API
- Ports `5433`, `5672`, `6379`, `1025`, `8025`, and `27017` free for local services

## 1 Minute Docker Launch

Start only the services needed for a local test:

```bash
docker compose up -d --build db rabbitmq redis mailhog mongo web worker
```

Check that the containers are running:

```bash
docker compose ps
```

Check the API:

```bash
curl http://localhost:8000/
curl http://localhost:8000/me
```

Open MailHog to inspect sent test emails:

```text
http://localhost:8025
```

## Local Service Ports

| Service | URL / port |
| --- | --- |
| API | `http://localhost:8000` |
| MailHog UI | `http://localhost:8025` |
| MailHog SMTP | `localhost:1025` |
| PostgreSQL | `localhost:5433` |
| RabbitMQ | `localhost:5672` |
| Redis | `localhost:6379` |
| MongoDB | `localhost:27017` |

Inside Docker, the app uses service names:

```text
db:5432
rabbitmq:5672
redis:6379
mailhog:1025
mongo:27017
```

## Send A Smoke Test Email

Create a local contact:

```bash
curl -X POST http://localhost:8000/contacts/add \
  -H "Content-Type: application/json" \
  -d '{"email":"test-recipient@example.com","name":"Test Recipient"}'
```

Send one direct email through the local SMTP container:

```bash
curl -X POST http://localhost:8000/send_email \
  -H "Content-Type: application/json" \
  -d '{"email":"test-recipient@example.com","from_email":"test@example.com","subject":"Docker smoke test","body":"Hello from Docker + MailHog"}'
```

Then open:

```text
http://localhost:8025
```

You should see the test email in MailHog.

## Logs

```bash
docker compose logs -f web
docker compose logs -f worker
```

## Stop Local Docker Services

```bash
docker compose down
```

To also remove local Docker volumes:

```bash
docker compose down -v
```

## Optional Tooling Containers

The compose file also contains optional admin/tooling services: Logto,
Elasticsearch, Kibana, Mongo Express, and Redis Commander. They are not required
for the 1 minute smoke test.

Start them only when needed:

```bash
docker compose --profile tools up -d
```

## SES Production Setup

For Amazon SES, domain DNS, Secrets Manager, and production preflight checks,
use:

```text
docs/ses-configuration.md
```
