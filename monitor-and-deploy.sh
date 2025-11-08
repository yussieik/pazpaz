#!/bin/bash
#
# Monitor CI/CD and Deploy When Ready
# This script watches GitHub Actions and deploys when CI passes
#

set -e

echo "🔍 Monitoring CI/CD Pipeline..."
echo "========================================"
echo ""

# Monitor CI runs
while true; do
    echo "Checking CI status..."

    # Get latest run status
    LATEST_RUN=$(gh run list --limit 1 --json status,conclusion,name,databaseId --jq '.[0]')
    STATUS=$(echo "$LATEST_RUN" | jq -r '.status')
    CONCLUSION=$(echo "$LATEST_RUN" | jq -r '.conclusion')
    NAME=$(echo "$LATEST_RUN" | jq -r '.name')
    RUN_ID=$(echo "$LATEST_RUN" | jq -r '.databaseId')

    echo "Latest Run: $NAME (ID: $RUN_ID)"
    echo "Status: $STATUS"
    echo "Conclusion: $CONCLUSION"
    echo ""

    # Check if completed
    if [ "$STATUS" = "completed" ]; then
        if [ "$CONCLUSION" = "success" ]; then
            echo "✅ CI PASSED! Deployment will start automatically..."
            echo ""
            echo "Waiting for Production Deployment workflow to complete..."
            sleep 30

            # Check deployment status
            DEPLOY_RUN=$(gh run list --workflow="Deploy Production" --limit 1 --json status,conclusion,databaseId --jq '.[0]')
            DEPLOY_STATUS=$(echo "$DEPLOY_RUN" | jq -r '.status')
            DEPLOY_CONCLUSION=$(echo "$DEPLOY_RUN" | jq -r '.conclusion')
            DEPLOY_ID=$(echo "$DEPLOY_RUN" | jq -r '.databaseId')

            echo "Deployment Run ID: $DEPLOY_ID"
            echo "Deployment Status: $DEPLOY_STATUS"

            if [ "$DEPLOY_STATUS" = "in_progress" ] || [ "$DEPLOY_STATUS" = "queued" ]; then
                echo "⏳ Deployment in progress, monitoring..."
                gh run watch $DEPLOY_ID
            fi

            # Final check
            FINAL_STATUS=$(gh run view $DEPLOY_ID --json conclusion --jq '.conclusion')
            if [ "$FINAL_STATUS" = "success" ]; then
                echo ""
                echo "================================================"
                echo "🎉 DEPLOYMENT SUCCESSFUL!"
                echo "================================================"
                echo ""
                echo "Your AI Agent is now LIVE in production!"
                echo ""
                echo "Next steps:"
                echo "1. Test AI chat at your production domain"
                echo "2. Monitor logs:"
                echo "   ssh pazpaz@5.161.241.81 'cd /opt/pazpaz && docker compose -f docker-compose.prod.yml --env-file .env.production logs -f api'"
                echo ""
                exit 0
            else
                echo "❌ Deployment failed with status: $FINAL_STATUS"
                echo "View logs: gh run view $DEPLOY_ID --log-failed"
                exit 1
            fi
        else
            echo "❌ CI FAILED with conclusion: $CONCLUSION"
            echo "View logs: gh run view $RUN_ID --log-failed"
            exit 1
        fi
    else
        echo "⏳ CI still running, waiting 10 seconds..."
        sleep 10
    fi
done
