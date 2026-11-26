// app-delivery: test -> build -> push -> rolling update -> smoke test, rollback if anything after deploy fails.
// Runs on the EC2 host (agent any). Jenkins credentials: ghcr-push (username/password), k3s-kubeconfig (secret file).
pipeline {
  agent any

  triggers {
    pollSCM('H/5 * * * *')            // GitHub cannot reach Jenkins: poll instead of webhooks
  }

  options {
    disableConcurrentBuilds()
    timeout(time: 30, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '20'))
  }

  environment {
    IMAGE           = 'ghcr.io/houssemchabbeh/registration-portal'
    PORTAL_URL      = 'http://172.24.4.73'    // node-a floating IP (Traefik)
    SMOKE_COURSE_ID = '6'                     // SMOKE-000 (hidden, capacity 100000), 6th row of app/seed.sql
    KUBECONFIG      = credentials('k3s-kubeconfig')
    TEST_PG         = "ci-pg-${env.BUILD_NUMBER}"
  }

  stages {
    stage('Version') {
      steps {
        script {
          env.TAG = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
          env.DEPLOYED = 'false'
        }
        echo "Image: ${IMAGE}:${TAG}"
      }
    }

    stage('Test') {
      steps {
        // Throwaway Postgres for the locking tests (they need a real database).
        sh '''
          podman run -d --rm --name "$TEST_PG" -e POSTGRES_PASSWORD=ci -e POSTGRES_DB=portal_test \
            -p 127.0.0.1:15432:5432 docker.io/library/postgres:17
          for i in $(seq 1 30); do
            podman exec "$TEST_PG" pg_isready -U postgres -d portal_test && break
            sleep 1
          done
          podman exec "$TEST_PG" pg_isready -U postgres -d portal_test
        '''
        // Same Python as the production image. conftest skips tests if the DB is unreachable,
        // so the DB is checked first: a skipped suite must never pass as green.
        sh '''
          podman run --rm --network host -v "$WORKSPACE/app:/src:Z" -w /src \
            -e TEST_DATABASE_URL=postgresql://postgres:ci@127.0.0.1:15432/portal_test \
            docker.io/library/python:3.12-slim sh -c '
              pip install -q -r requirements-dev.txt &&
              python -c "import os, psycopg; psycopg.connect(os.environ[\\"TEST_DATABASE_URL\\"], connect_timeout=3).close()" &&
              pytest -q --junitxml=report.xml'
        '''
      }
      post {
        always {
          junit testResults: 'app/report.xml', allowEmptyResults: true
          sh 'podman rm -f "$TEST_PG" || true'
        }
      }
    }

    stage('Build') {
      steps {
        sh 'podman build -t "$IMAGE:$TAG" -f app/Containerfile app'
      }
    }

    stage('Push') {
      steps {
        withCredentials([usernamePassword(credentialsId: 'ghcr-push', usernameVariable: 'GHCR_USER', passwordVariable: 'GHCR_TOKEN')]) {
          sh '''
            echo "$GHCR_TOKEN" | podman login ghcr.io --username "$GHCR_USER" --password-stdin
            podman push "$IMAGE:$TAG"
          '''
        }
      }
    }

    stage('Deploy') {
      steps {
        script { env.DEPLOYED = 'true' }      // from here on, a failure triggers the rollback
        sh '''
          kubectl -n registration set image deployment/web web="$IMAGE:$TAG"
          kubectl -n registration annotate deployment/web kubernetes.io/change-cause="jenkins #$BUILD_NUMBER $TAG" --overwrite
          kubectl -n registration rollout status deployment/web --timeout=180s
        '''
      }
    }

    stage('Smoke test') {
      steps {
        // A real registration on the hidden course, then read the receipt back, then the invariants.
        sh '''
          STUDENT="smoke-$BUILD_NUMBER-$(date +%s)"
          OUT=$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -X POST "$PORTAL_URL/register" \
                  -d "student_id=$STUDENT" -d "course_id=$SMOKE_COURSE_ID")
          echo "register -> $OUT"
          CODE=${OUT%% *}; LOCATION=${OUT#* }
          [ "$CODE" = "303" ] || { echo "expected 303"; exit 1; }
          case "$LOCATION" in */receipt/REG-*) ;; *) echo "no receipt in redirect"; exit 1 ;; esac
          curl -sf -o /dev/null "$LOCATION"
          echo "receipt page OK: $LOCATION"
          curl -sf "$PORTAL_URL/admin/check"
          echo
        '''
      }
    }
  }

  post {
    failure {
      script {
        if (env.DEPLOYED == 'true') {
          echo 'Failure after deploy: rolling back to the previous ReplicaSet'
          sh '''
            kubectl -n registration rollout undo deployment/web
            kubectl -n registration rollout status deployment/web --timeout=180s
            kubectl -n registration rollout history deployment/web
          '''
        }
      }
    }
    always {
      sh 'podman logout ghcr.io || true'
    }
  }
}
