# Production Deployment

This repository is ready for a `GitHub Actions self-hosted runner on EC2 -> docker compose up -d --build` workflow.

## Files used for deployment

- `Backend/docker-compose.prod.yml`: production compose file that builds containers directly on EC2
- `Backend/.env.prod.example`: template for the EC2 runtime environment file
- `.github/workflows/deploy-prod.yml`: CI/CD workflow that runs directly on the EC2 self-hosted runner

## One-time EC2 setup

1. Install Docker, Docker Compose plugin, `curl`, `tar`, and `unzip`.
2. Create a deployment directory, for example `/opt/healthcare`.
3. Create `/opt/healthcare/.env.prod` from `Backend/.env.prod.example` and replace every placeholder value.
4. Install a GitHub self-hosted runner on the same EC2 instance.
5. Run the runner with the default labels so the workflow can target `self-hosted`, `linux`, and `x64`.
6. Make sure the runner user can run Docker commands and can write to the deploy directory.

## GitHub configuration

Create this environment variable in the `production` environment:

- `EC2_DEPLOY_PATH`

You no longer need these values for the current workflow:

- `AWS_REGION`
- `ECR_REGISTRY`
- `AWS_ROLE_TO_ASSUME`
- `EC2_HOST`
- `EC2_USER`
- `EC2_SSH_PRIVATE_KEY`

## Deploy flow

1. Push to `main` or run the workflow manually.
2. The self-hosted runner on EC2 checks out the repository.
3. The workflow copies the `Backend` folder into the deploy directory on the same server.
4. The workflow runs `docker compose up -d --build --remove-orphans` locally on EC2.
5. The workflow verifies the gateway health endpoint.

## Install the self-hosted runner on EC2

On the EC2 instance, run these preparation commands from a normal user such as `ubuntu`:

```bash
mkdir -p ~/actions-runner && cd ~/actions-runner
```

Then in GitHub:

1. Go to `Repository -> Settings -> Actions -> Runners`.
2. Click `New self-hosted runner`.
3. Choose `Linux` and `x64`.
4. GitHub will show you the exact download command for the current runner version. Run that command on EC2 inside `~/actions-runner`.
5. GitHub will then show you the exact `./config.sh --url ... --token ...` command. Run it on EC2 in the same directory.
6. Accept the default labels so the runner keeps `self-hosted`, `Linux`, and `X64`.

After that, install the runner as a service:

```bash
cd ~/actions-runner
sudo ./svc.sh install ubuntu
sudo ./svc.sh start
sudo ./svc.sh status
```

If Docker commands fail for the runner user, add the user to the Docker group and log in again:

```bash
sudo usermod -aG docker ubuntu
```

If the deploy directory needs write access for the runner user:

```bash
sudo mkdir -p /opt/healthcare
sudo chown -R ubuntu:ubuntu /opt/healthcare
```

## Rollback

This flow is source-based, not image-tag-based.

To roll back, redeploy an older commit by reverting `main` to a known-good state or by rerunning the workflow from a branch/tag that points to the older version you want to restore.

## Notes for this project

- Only `api-gateway` is exposed publicly in `docker-compose.prod.yml`.
- `users-service` and `api-gateway` read deploy-sensitive values from environment variables.
- The deploy workflow now builds and runs the containers directly on the EC2 host, so it does not require ECR or SSH from GitHub-hosted runners.
- If GitHub still blocks all Actions because of an account billing lock, you must clear that lock before any workflow, including self-hosted ones, can start.
