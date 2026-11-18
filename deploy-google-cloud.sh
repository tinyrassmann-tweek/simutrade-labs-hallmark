#!/usr/bin/env bash
set -euo pipefail
# Run in Google Cloud Shell from this directory. Uses your chosen existing project.
# Cloud resources can incur charges; max=1 and min=0 reduce idle compute use but are not a spending cap.
ST_PROJECT="${1:?Usage: bash deploy-google-cloud.sh PROJECT_ID REGION OWNER_EMAIL}"
ST_REGION="${2:-us-central1}"
ST_OWNER="${3:?Provide the email you will use for the owner account}"
[[ "$ST_PROJECT" =~ ^[a-z][a-z0-9-]{4,61}[a-z0-9]$ ]] || { echo 'Invalid project ID'; exit 1; }
[[ "$ST_REGION" =~ ^[a-z]+-[a-z]+[0-9]$ ]] || { echo 'Invalid region'; exit 1; }
[[ "$ST_OWNER" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]] || { echo 'Invalid owner email'; exit 1; }
command -v gcloud >/dev/null || { echo 'Open Google Cloud Shell, where gcloud is preinstalled.'; exit 1; }
cd "$(dirname "$0")"
gcloud projects describe "$ST_PROJECT" --format='value(projectId)' >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com secretmanager.googleapis.com --project="$ST_PROJECT" --quiet
ST_RUNTIME="simutrade-runtime@${ST_PROJECT}.iam.gserviceaccount.com"
ST_BUILDER="simutrade-builder@${ST_PROJECT}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$ST_RUNTIME" --project="$ST_PROJECT" >/dev/null 2>&1; then
 gcloud iam service-accounts create simutrade-runtime --display-name='SimuTrade runtime' --project="$ST_PROJECT" --quiet
fi
if ! gcloud iam service-accounts describe "$ST_BUILDER" --project="$ST_PROJECT" >/dev/null 2>&1; then
 gcloud iam service-accounts create simutrade-builder --display-name='SimuTrade source builder' --project="$ST_PROJECT" --quiet
fi
gcloud projects add-iam-policy-binding "$ST_PROJECT" --member="serviceAccount:$ST_RUNTIME" --role=roles/datastore.user --quiet >/dev/null
gcloud projects add-iam-policy-binding "$ST_PROJECT" --member="serviceAccount:$ST_BUILDER" --role=roles/run.builder --quiet >/dev/null
if ! gcloud firestore databases describe --database='(default)' --project="$ST_PROJECT" >/dev/null 2>&1; then
 gcloud firestore databases create --database='(default)' --location="$ST_REGION" --type=firestore-native --project="$ST_PROJECT" --quiet
fi
ST_DBTYPE="$(gcloud firestore databases describe --database='(default)' --project="$ST_PROJECT" --format='value(type)')"
[[ "$ST_DBTYPE" == 'FIRESTORE_NATIVE' ]] || { echo 'The default database must use Firestore Native mode.'; exit 1; }
if ! gcloud secrets describe simutrade-owner-token --project="$ST_PROJECT" >/dev/null 2>&1; then
 python3 -c 'import secrets;print(secrets.token_urlsafe(48),end="")' | gcloud secrets create simutrade-owner-token --replication-policy=automatic --data-file=- --project="$ST_PROJECT" --quiet
fi
gcloud secrets add-iam-policy-binding simutrade-owner-token --member="serviceAccount:$ST_RUNTIME" --role=roles/secretmanager.secretAccessor --project="$ST_PROJECT" --quiet >/dev/null
gcloud run deploy simutrade-labs --source=. --project="$ST_PROJECT" --region="$ST_REGION" --service-account="$ST_RUNTIME" --build-service-account="projects/$ST_PROJECT/serviceAccounts/$ST_BUILDER" --allow-unauthenticated --min=0 --max=1 --concurrency=20 --cpu=1 --memory=512Mi --timeout=60 --set-env-vars="GOOGLE_CLOUD_PROJECT=$ST_PROJECT,ADMIN_EMAIL=$ST_OWNER" --set-secrets='ADMIN_ACCESS_TOKEN=simutrade-owner-token:latest' --quiet
gcloud run services describe simutrade-labs --project="$ST_PROJECT" --region="$ST_REGION" --format='value(status.url)'
