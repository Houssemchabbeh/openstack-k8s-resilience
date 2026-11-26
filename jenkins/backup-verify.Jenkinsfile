// backup-verify (nightly): latest dump from Swift -> restore into a throwaway Postgres -> invariants.
// Fails if: no dump, dump older than MAX_AGE_MIN, restore error, or a broken invariant.
// Never touches the cluster. Jenkins credential: openstack-clouds-yaml (secret file, app-cred cloud only).
pipeline {
  agent any

  triggers {
    cron('H 2 * * *')                 // once a night, minute chosen by Jenkins
  }

  options {
    disableConcurrentBuilds()
    timeout(time: 20, unit: 'MINUTES')
    buildDiscarder(logRotator(numToKeepStr: '30'))
  }

  environment {
    OS_CLIENT_CONFIG_FILE = credentials('openstack-clouds-yaml')
    OS_CLOUD              = 'resilience-appcred'
    CONTAINER             = 'registration-backups'
    MAX_AGE_MIN           = '30'      // CronJob runs every 15 min: older than 30 = backups have stopped
    VERIFY_PG             = "verify-pg-${env.BUILD_NUMBER}"
  }

  stages {
    stage('Fetch latest dump') {
      steps {
        sh '''
          LATEST=$(openstack object list "$CONTAINER" --prefix registration- -f value -c Name | sort | tail -1)
          [ -n "$LATEST" ] || { echo "no backup in $CONTAINER"; exit 1; }
          openstack object save --file latest.dump "$CONTAINER" "$LATEST"
          echo "$LATEST" > latest.txt
          ls -l latest.dump; echo "latest: $LATEST"
        '''
      }
    }

    stage('Freshness') {
      steps {
        // registration-20261126T1045Z.dump -> "20261126 10:45" UTC
        sh '''
          WHEN=$(sed -E 's/^registration-([0-9]{8})T([0-9]{2})([0-9]{2})Z\\.dump$/\\1 \\2:\\3/' latest.txt)
          AGE_MIN=$(( ($(date -u +%s) - $(date -u -d "$WHEN" +%s)) / 60 ))
          echo "latest backup is $AGE_MIN min old (limit $MAX_AGE_MIN)"
          [ "$AGE_MIN" -le "$MAX_AGE_MIN" ]
        '''
      }
    }

    stage('Restore') {
      steps {
        sh '''
          podman run -d --rm --name "$VERIFY_PG" -e POSTGRES_PASSWORD=verify -e POSTGRES_DB=registration \
            docker.io/library/postgres:17
          for i in $(seq 1 30); do
            podman exec "$VERIFY_PG" pg_isready -U postgres -d registration && break
            sleep 1
          done
          # --no-owner: role "portal" does not exist here. --exit-on-error: any error fails the build.
          podman exec -i "$VERIFY_PG" pg_restore -U postgres -d registration --no-owner --exit-on-error < latest.dump
        '''
      }
    }

    stage('Invariants') {
      steps {
        // Same queries as app/portal/checks.py.
        sh '''
          q() { podman exec "$VERIFY_PG" psql -U postgres -d registration -tAc "$1"; }
          COURSES=$(q "SELECT count(*) FROM courses")
          REGS=$(q "SELECT count(*) FROM registrations")
          MISMATCHES=$(q "SELECT count(*) FROM (SELECT c.id FROM courses c LEFT JOIN registrations r ON r.course_id = c.id GROUP BY c.id HAVING c.seats_taken <> count(r.id)) m")
          OVERBOOKED=$(q "SELECT count(*) FROM courses WHERE seats_taken > capacity")
          DUPLICATES=$(q "SELECT count(*) FROM (SELECT 1 FROM registrations GROUP BY student_id, course_id HAVING count(*) > 1) d")
          {
            echo "dump:          $(cat latest.txt)"
            echo "courses:       $COURSES"
            echo "registrations: $REGS"
            echo "seat_mismatch: $MISMATCHES"
            echo "overbooked:    $OVERBOOKED"
            echo "duplicates:    $DUPLICATES"
          } | tee invariants.txt
          [ "$COURSES" -gt 0 ] && [ "$MISMATCHES" -eq 0 ] && [ "$OVERBOOKED" -eq 0 ] && [ "$DUPLICATES" -eq 0 ]
        '''
      }
    }
  }

  post {
    always {
      archiveArtifacts artifacts: 'latest.txt, invariants.txt', allowEmptyArchive: true
      // The dump holds student data: never left in the workspace.
      sh 'podman rm -f "$VERIFY_PG" || true; rm -f latest.dump'
    }
  }
}
