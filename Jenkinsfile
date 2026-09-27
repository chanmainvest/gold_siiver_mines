// Jenkins pipeline: nightly refresh of the DuckDB price cache + static site rebuild.
//
// What it does (mirrors .github/workflows/nightly-prices.yml):
//   1. checks out this repo
//   2. pip-installs duckdb
//   3. python3 scripts/fetch_price_history.py --incremental   (Yahoo Finance -> data/prices.duckdb)
//   4. python3 scripts/build_website.py                       (data/webapp + duckdb -> index.html)
//   5. commits data/prices.duckdb, data/ticker_map.json, index.html and pushes,
//      so GitHub Pages redeploys with fresh charts.
//
// Setup required in Jenkins:
//   - a username/password (or token) credential with push access to
//     github.com/chanmainvest/gold_siiver_mines; put its credentialsId in
//     GIT_CREDENTIALS below. For a fine-grained PAT, username can be anything.
//   - an agent with python3, pip and git.

pipeline {
  agent any

  triggers {
    cron('H 8 * * *')   // nightly, hashed minute to spread load
  }

  environment {
    GIT_CREDENTIALS = 'github-push'   // <-- Jenkins credentialsId for git push
    GIT_REPO = 'github.com/chanmainvest/gold_siiver_mines.git'
  }

  stages {
    stage('Checkout') {
      steps {
        checkout scm
      }
    }

    stage('Setup') {
      steps {
        sh 'python3 -m pip install --user duckdb pandas'
      }
    }

    stage('Fetch prices') {
      steps {
        sh 'python3 scripts/fetch_price_history.py --incremental'
      }
    }

    stage('Rebuild site') {
      steps {
        sh 'python3 scripts/build_website.py'
      }
    }

    stage('Commit & push') {
      steps {
        withCredentials([usernamePassword(credentialsId: env.GIT_CREDENTIALS,
                                           usernameVariable: 'GIT_USER',
                                           passwordVariable: 'GIT_PASS')]) {
          sh '''
            set -e
            git config user.name "jenkins"
            git config user.email "jenkins@localhost"
            git add data/prices.duckdb data/ticker_map.json index.html
            if git diff --cached --quiet; then
              echo "no changes"
            else
              git commit -m "Nightly: refresh price history ($(date -u +%F))"
              git push "https://${GIT_USER}:${GIT_PASS}@${GIT_REPO}" HEAD:main
            fi
          '''
        }
      }
    }
  }

  post {
    failure {
      echo 'Nightly price refresh failed — check the Fetch prices / Rebuild site stage logs.'
    }
  }
}
