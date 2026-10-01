# how to deploy

## local

```bash
cd infra
docker compose up --build
```

---

## prod

```bash
sudo su - ubuntu
cd ~/proctor-suite/infra
sudo docker compose up -d --build
bash ~/proctor-suite/infra/deploy.sh
```
